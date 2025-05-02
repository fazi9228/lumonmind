from flask import Flask, request, jsonify
import os
import json
import requests
import sys
import io
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta
import uuid
import re
from flask_cors import CORS  # Import CORS for cross-origin support
from flask import send_from_directory

# Silence stderr to prevent "No secrets found" messages
old_stderr = sys.stderr
sys.stderr = io.StringIO()

# Now it's safe to import potentially noisy modules
try:
    import google.generativeai as genai
except ImportError:
    # Will handle this later
    pass

# Restore stderr
sys.stderr = old_stderr

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})  # Enable CORS for all routes with proper configuration

# Constants - Updated model names to ensure they're current
DEEPSEEK_MODEL = "deepseek-v3"  # Updated from "deepseek-chat"
QWEN_MODEL = "qwen-max"  # Updated from "qwen-max"
GEMINI_MODEL = "gemini-2.0"  # Updated from "gemini-1.5-pro-latest"

# Dictionary to store session data
sessions = {}
# Dictionary of keywords for topic detection
TOPIC_KEYWORDS = {
    'anxiety': [
        'anxious', 'anxiety', 'worry', 'worrying', 'panic', 'stressed', 
        'overthinking', 'nervous', 'fear', 'scared', 'tense', 'racing heart',
        'cant breathe', 'chest tight', 'what if', 'overthink', 'catastrophe',
        'afraid', 'terrified', 'phobia', 'worried', 'on edge', 'restless'
    ],
    'depression': [
        'depressed', 'depression', 'sad', 'hopeless', 'unmotivated', 'worthless',
        'tired all the time', 'no energy', 'no interest', 'empty', 'numb', 
        'cant enjoy', 'no pleasure', 'pointless', 'dont care anymore',
        'giving up', 'why bother', 'no future', 'meaningless', 'exhausted',
        'no point', 'miserable', 'alone', 'cant get out of bed', 'apathy'
    ],
    'grief': [
        'grief', 'loss', 'died', 'death', 'passed away', 'deceased', 'bereavement',
        'lost my', 'funeral', 'missing someone', 'anniversary of', 'grieving',
        'mourning', 'cope with loss', 'they\'re gone', 'widow', 'widower',
        'remembrance', 'gone forever', 'never see them again', 'memorial'
    ],
    'sleep': [
        'insomnia', 'cant sleep', 'trouble sleeping', 'tired', 'exhausted',
        'wake up', 'nightmares', 'bad dreams', 'sleep schedule', 'oversleeping',
        'cant fall asleep', 'lying awake', 'racing thoughts at night', 'sleep quality',
        'keep waking up', 'early morning', 'bedtime', 'sleeping pills', 'fatigue'
    ],
    'relationship': [
        'marriage', 'partner', 'boyfriend', 'girlfriend', 'spouse', 'relationship',
        'breakup', 'divorce', 'arguing', 'communication', 'trust issues', 'cheating',
        'ex', 'dating', 'love', 'commitment', 'jealous', 'affair', 'fighting', 
        'unhappy together', 'toxic relationship', 'boundaries', 'controlling'
    ],
    'stress-burnout': [
        'stress', 'burnout', 'overwhelmed', 'workload', 'overworked', 'pressure',
        'too much', 'cant keep up', 'deadline', 'balance', 'time management',
        'no time', 'exhaustion', 'drained', 'depleted', 'cant do it all',
        'breaking point', 'overload', 'responsibilities', 'burden'
    ],
    'self-esteem': [
        'hate myself', 'not good enough', 'failure', 'ugly', 'worthless',
        'stupid', 'inadequate', 'incompetent', 'self-doubt', 'imposter',
        'fraud', 'unlovable', 'unworthy', 'ashamed', 'body image', 'fat',
        'unattractive', 'comparison', 'perfectionist', 'low confidence'
    ]
}

# Add these routes to serve static files
@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

# Test route for verifying the API is running
@app.route('/test', methods=['GET'])
def test_route():
    return jsonify({"status": "ok", "message": "Test route is working"})

# Enhanced API key handling with multiple fallback mechanisms

# Enhanced API key handling with verification
def get_api_key(provider="qwen"):
    """
    Get the API key from environment variable with validation
    
    Args:
        provider (str): The API provider ("qwen", "deepseek", or "gemini")
    """
    env_var_names = {
        "qwen": ["QWEN_API_KEY"],
        "deepseek": ["DEEPSEEK_API_KEY"],
        "gemini": ["GEMINI_API_KEY"]
    }
    
    # Check environment variables (loaded from .env file)
    for env_var in env_var_names.get(provider, []):
        api_key = os.getenv(env_var)
        if api_key:
            # Basic validation - API keys should be at least 20 chars
            if len(api_key.strip()) < 20:
                print(f"WARNING: {provider} API key found but may be invalid (too short).")
                return None
            return api_key.strip()  # Trim any whitespace
    
    # No API key found
    return None

# Run API verification at startup
def verify_api_keys():
    """Verify API keys at application startup"""
    print("Verifying API keys...")
    
    qwen_key = get_api_key("qwen")
    deepseek_key = get_api_key("deepseek")
    gemini_key = get_api_key("gemini")
    
    if not any([qwen_key, deepseek_key, gemini_key]):
        print("WARNING: No valid API keys found. The application will not be able to generate responses.")
        print("Please ensure you have at least one of the following environment variables set:")
        print("  - QWEN_API_KEY (for Alibaba Cloud's Qwen Max model)")
        print("  - DEEPSEEK_API_KEY (for DeepSeek Chat model)")
        print("  - GEMINI_API_KEY (for Google's Gemini model)")
        print("\nYou can set these in a .env file in the same directory as this script.")
        print("Example .env file contents:")
        print("QWEN_API_KEY=your_qwen_api_key_here")
        print("DEEPSEEK_API_KEY=your_deepseek_api_key_here")
        print("GEMINI_API_KEY=your_gemini_api_key_here")
    else:
        print(f"API keys found: Qwen: {'Yes' if qwen_key else 'No'}, "
              f"DeepSeek: {'Yes' if deepseek_key else 'No'}, "
              f"Gemini: {'Yes' if gemini_key else 'No'}")
        
    return qwen_key, deepseek_key, gemini_key

# Get API keys with the function
DEEPSEEK_API_KEY = get_api_key("deepseek")
QWEN_API_KEY = get_api_key("qwen")
GEMINI_API_KEY = get_api_key("gemini")

# For testing, provide fallback API keys if none are found
if not any([DEEPSEEK_API_KEY, QWEN_API_KEY, GEMINI_API_KEY]):
    print("WARNING: No API keys found in environment. Using fallback mock API mode.")
    # Set a mock API mode flag
    MOCK_API_MODE = True
else:
    MOCK_API_MODE = False

# Load the prompt template - critical for operation
def load_prompt_template():
    try:
        # Try to load from the local file
        prompt_path = os.path.join(os.path.dirname(__file__), "lumonmind_prompt.md")
        
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_content = f.read()
                if not prompt_content or len(prompt_content.strip()) < 10:
                    print("ERROR: Prompt file exists but appears to be empty or too short.")
                    # Return a fallback prompt instead of exiting
                    return """You are LumonMind, an AI mental health companion. Your goal is to provide support, 
                           empathy, and helpful information to users experiencing mental health challenges.
                           Always be supportive, non-judgmental, and compassionate."""
                return prompt_content
        else:
            # If no prompt file found, use a fallback prompt instead of exiting
            print("WARNING: Prompt file not found. Using fallback prompt.")
            return """You are LumonMind, an AI mental health companion. Your goal is to provide support, 
                   empathy, and helpful information to users experiencing mental health challenges.
                   Always be supportive, non-judgmental, and compassionate."""
    except Exception as e:
        print(f"WARNING: Cannot load prompt template: {e}. Using fallback prompt.")
        return """You are LumonMind, an AI mental health companion. Your goal is to provide support, 
               empathy, and helpful information to users experiencing mental health challenges.
               Always be supportive, non-judgmental, and compassionate."""

# Load prompt template
SYSTEM_PROMPT = load_prompt_template()

# Add language support information to the prompt
SYSTEM_PROMPT += """

## Language Support
You are capable of understanding multiple languages, including:
1. English
2. Hindi in Roman script (Hinglish/Romanized Hindi)
3. Many other languages

If users write in Romanized Hindi (Hindi written using English letters), please:
1. Understand their message completely
2. Respond in the SAME language format they used
3. NEVER convert Romanized Hindi to Devanagari script
4. NEVER explain that you understand Hindi or mention language switching

Example Hinglish/Romanized Hindi phrases you should understand:
- "Main bahut tension mein hoon" (respond in same Roman script)
- "Mujhe neend nahi aati hai" (respond in same Roman script)
- "Main bahut pareshan feel kar raha hoon" (respond in same Roman script)
- "Maa-baap naraz hai mujhse" (respond in same Roman script)
- "Log kya kahenge" (respond in same Roman script)

Always maintain the user's language choice and format in your responses.
"""

# File paths for extensions
def get_extension_path(topic):
    """Get file path for a topic extension"""
    # Update this path based on your directory structure
    base_path = os.path.dirname(os.path.abspath(__file__))
    extensions_dir = os.path.join(base_path, "extensions")
    
    # Create extensions directory if it doesn't exist
    if not os.path.exists(extensions_dir):
        os.makedirs(extensions_dir)
    
    return os.path.join(extensions_dir, f"{topic}_extension.md")


def load_extension(topic):
    """Load a specific topic extension content"""
    try:
        extension_path = get_extension_path(topic)
        if os.path.exists(extension_path):
            with open(extension_path, 'r', encoding='utf-8') as file:
                return file.read()
        else:
            print(f"Extension file not found for topic: {topic}")
            return None
    except Exception as e:
        print(f"Error loading extension for {topic}: {str(e)}")
        return None


def detect_mental_health_topics(messages, message_threshold=5, keyword_threshold=3):
    """
    Analyze conversation to detect mental health topics
    
    Args:
        messages: List of message dictionaries with 'role' and 'content'
        message_threshold: Number of most recent messages to analyze
        keyword_threshold: Minimum keyword matches to identify a topic
    
    Returns:
        List of detected topics ordered by relevance
    """
    # Extract recent user messages
    user_messages = [msg['content'] for msg in messages 
                    if msg.get('role') == 'user'][-message_threshold:]
    
    # Combine into one text for analysis
    combined_text = ' '.join(user_messages).lower()
    
    # Count keyword matches for each topic
    topic_counts = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        count = 0
        for keyword in keywords:
            # Use word boundary regex to find whole word matches
            matches = re.findall(r'\b' + re.escape(keyword) + r'\b', combined_text)
            count += len(matches)
        topic_counts[topic] = count
    
    # Filter topics that meet the threshold
    detected_topics = [topic for topic, count in topic_counts.items() 
                      if count >= keyword_threshold]
    
    # Sort by relevance (keyword count)
    detected_topics.sort(key=lambda x: topic_counts[x], reverse=True)
    
    # Log detection results
    print(f"Topic detection results: {topic_counts}")
    print(f"Detected topics: {detected_topics}")
    
    return detected_topics


def apply_topic_extensions(messages, session_data=None):
    """
    Analyze messages and apply relevant topic extensions to the system prompt
    
    Args:
        messages: List of message dictionaries
        session_data: Optional session data dictionary for tracking
    
    Returns:
        Modified messages list with updated system prompt
    """
    # Create a deep copy of messages to avoid modifying the original
    modified_messages = [msg.copy() for msg in messages]
    
    # Detect topics in the conversation
    detected_topics = detect_mental_health_topics(messages)
    
    # If no topics detected or no system message, return original
    if not detected_topics:
        return modified_messages
    
    # Find the system message
    system_index = None
    for i, msg in enumerate(modified_messages):
        if msg.get('role') == 'system':
            system_index = i
            break
    
    if system_index is None:
        print("No system message found to modify")
        return modified_messages
    
    # Load extensions for detected topics (limit to top 2)
    extensions = []
    for topic in detected_topics[:2]:  # Limit to top 2 most relevant topics
        extension_content = load_extension(topic)
        if extension_content:
            extensions.append(extension_content)
    
    # Update the system message with extensions
    if extensions:
        modified_messages[system_index]['content'] += "\n\n" + "\n\n".join(extensions)
        
        # Log the modification
        print(f"Applied topic extensions: {detected_topics[:2]}")
        
        # Update session data if provided
        if session_data is not None:
            session_data['applied_extensions'] = detected_topics[:2]
            session_data['extension_applied_at'] = datetime.now().isoformat()
    
    return modified_messages


def flask_implementation(session_id, messages):
    """
    Implementation for Flask API version
    
    Args:
        session_id: The session identifier
        messages: The message list
    
    Returns:
        Modified messages with appropriate extensions
    """
    # Get or initialize session data
    if session_id not in sessions:
        return messages
    
    session = sessions[session_id]
    
    # Initialize extension tracking in session data if not present
    if 'applied_extensions' not in session:
        session['applied_extensions'] = []
    
    if 'extension_applied_at' not in session:
        session['extension_applied_at'] = None
    
    # Create session data dictionary for tracking
    session_data = {
        'applied_extensions': session.get('applied_extensions', []),
        'extension_applied_at': session.get('extension_applied_at')
    }
    
    # Apply extensions and update session
    modified_messages = apply_topic_extensions(messages, session_data)
    
    # Update session with any changes
    session['applied_extensions'] = session_data.get('applied_extensions', [])
    session['extension_applied_at'] = session_data.get('extension_applied_at')
    
    return modified_messages


# Function to detect therapist/counselor requests
def detect_therapist_request(user_message):
    """Detect if user is requesting to speak with a human therapist or counselor"""
    therapist_keywords = [
        "talk to a therapist", "speak to a therapist", 
        "talk to a counselor", "speak to a counselor",
        "human therapist", "real therapist", 
        "book appointment", "schedule appointment",
        "see a professional", "talk to a professional",
        "book a session", "talk to a human",
        "need real help", "want real help",
        "see a therapist", "therapist appointment",
        "need a therapist", "want a therapist",
        "consult with a counselor", "meet with a therapist"
    ]
    
    # Case-insensitive check for any keyword
    user_message_lower = user_message.lower()
    for keyword in therapist_keywords:
        if keyword in user_message_lower:
            return True
    return False

# Mock API response for testing when no API keys are available
def mock_ai_response(messages):
    """Generate a mock AI response for testing when no API keys are available"""
    user_messages = [msg['content'] for msg in messages if msg.get('role') == 'user']
    if not user_messages:
        return "Hello! I'm LumonMind, your AI mental health companion. How can I help you today?", "mock"
        
    last_message = user_messages[-1].lower()
    
    # Simple keyword-based responses
    if any(word in last_message for word in ['hello', 'hi', 'hey']):
        return "Hi there! How are you feeling today?", "mock"
    elif any(word in last_message for word in ['sad', 'depressed', 'unhappy']):
        return "I'm sorry to hear you're feeling this way. Would you like to talk about what's making you feel sad?", "mock"
    elif any(word in last_message for word in ['anxious', 'anxiety', 'worried']):
        return "Anxiety can be really challenging. Let's talk about what's causing your anxiety and explore some coping strategies.", "mock"
    elif any(word in last_message for word in ['sleep', 'tired', 'insomnia']):
        return "Sleep problems can have a big impact on our mental health. Have you noticed any patterns with your sleep difficulties?", "mock"
    elif any(word in last_message for word in ['relationship', 'partner', 'friend']):
        return "Relationships can be complex. Would you like to share more about what's happening in this relationship?", "mock"
    else:
        return "Thank you for sharing that with me. Could you tell me more about how this is affecting you?", "mock"
    
# Helper functions for API calls - Completely rewritten for reliability
def call_qwen_api(messages):
    """Call the Qwen API through Alibaba Cloud using OpenAI client"""
    try:
        if not QWEN_API_KEY:
            print("Qwen API key is missing.")
            return None, None
            
        try:
            # Use OpenAI client with Alibaba Cloud's DashScope endpoint
            from openai import OpenAI
            
            # Try both endpoints to increase chances of success
            # Some regions work better with different endpoints
            endpoints = [
                "https://dashscope.aliyuncs.com/v1",
                "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
            ]
            
            # Print API key (first few characters for debugging)
            print(f"Using Qwen API key: {QWEN_API_KEY[:5]}...")
            
            # Convert messages for Qwen API - ensure all have role and content
            api_messages = []
            for msg in messages:
                if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                    # Make sure content is string
                    if not isinstance(msg['content'], str):
                        msg['content'] = str(msg['content'])
                    api_messages.append({
                        'role': msg['role'],
                        'content': msg['content']
                    })
            
            # Debug logging
            print("Sending to Qwen API:", json.dumps(api_messages, indent=2)[:500] + "...")
            
            # Try each endpoint until one works
            last_error = None
            for endpoint in endpoints:
                try:
                    print(f"Trying Qwen API endpoint: {endpoint}")
                    client = OpenAI(
                        api_key=QWEN_API_KEY,
                        base_url=endpoint
                    )
                    
                    completion = client.chat.completions.create(
                        model=QWEN_MODEL,
                        messages=api_messages,
                        temperature=0.7,
                        max_tokens=2000,
                        timeout=60  # Increased timeout to 60 seconds
                    )
                    
                    # Extract content from response
                    content = completion.choices[0].message.content
                    print(f"Qwen API returned content of length: {len(content)}")
                    return content, "qwen"
                    
                except Exception as e:
                    print(f"Qwen API Error with endpoint {endpoint}: {str(e)}")
                    last_error = e
                    continue  # Try the next endpoint
            
            # If we get here, all endpoints failed
            print(f"All Qwen API endpoints failed. Last error: {str(last_error)}")
            log_dir = os.path.join(os.path.dirname(__file__), "logs")
            os.makedirs(log_dir, exist_ok=True)
            error_log = os.path.join(log_dir, f"error_log_{datetime.now().strftime('%Y%m%d')}.txt")
            with open(error_log, "a") as f:
                f.write(f"[{datetime.now().isoformat()}] All Qwen API endpoints failed. Last error: {str(last_error)}\n")
            return None, None
                
        except ImportError:
            print("OpenAI module not installed. Please run: pip install openai>=1.0.0")
            return None, None
            
    except Exception as e:
        print(f"Qwen API failed with error: {e}")
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        error_log = os.path.join(log_dir, f"error_log_{datetime.now().strftime('%Y%m%d')}.txt")
        with open(error_log, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] Qwen Exception: {str(e)}\n")
        return None, None
    
def call_deepseek_api(messages):
    """Call the DeepSeek API with improved error handling and reliability"""
    try:
        if not DEEPSEEK_API_KEY:
            print("DeepSeek API key is missing.")
            return None, None
            
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Print API key (first few characters for debugging)
        print(f"Using DeepSeek API key: {DEEPSEEK_API_KEY[:5]}...")
        
        # Properly format messages for DeepSeek API
        api_messages = []
        for msg in messages:
            if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                # Make sure content is string
                if not isinstance(msg['content'], str):
                    msg['content'] = str(msg['content'])
                # Handle system role (DeepSeek uses 'system' role)
                api_messages.append({
                    'role': msg['role'],
                    'content': msg['content']
                })
        
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": api_messages,
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        # Debug logging
        print("Sending to DeepSeek API:", json.dumps(api_messages, indent=2)[:500] + "...")
        
        # Try both endpoints to increase chances of success
        endpoints = [
            "https://api.deepseek.com/v1/chat/completions",
            "https://api.deepseek.ai/v1/chat/completions"  # Alternative endpoint
        ]
        
        last_error = None
        for endpoint_url in endpoints:
            try:
                print(f"Calling DeepSeek API at: {endpoint_url}")
                
                response = requests.post(
                    endpoint_url,
                    headers=headers,
                    json=payload,
                    timeout=60  # Increased timeout to 60 seconds
                )
                
                print(f"DeepSeek API Response Status: {response.status_code}")
                
                if response.status_code == 200:
                    response_json = response.json()
                    print(f"DeepSeek API Response: {response_json}")
                    return response_json["choices"][0]["message"]["content"], "deepseek"
                else:
                    print(f"DeepSeek API Error with endpoint {endpoint_url}: {response.text}")
                    last_error = response.text
                    continue  # Try the next endpoint
            except requests.exceptions.RequestException as e:
                print(f"DeepSeek API connection error with endpoint {endpoint_url}: {str(e)}")
                last_error = str(e)
                continue  # Try the next endpoint
        
        # If we get here, all endpoints failed
        print(f"All DeepSeek API endpoints failed. Last error: {last_error}")
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        error_log = os.path.join(log_dir, f"error_log_{datetime.now().strftime('%Y%m%d')}.txt")
        with open(error_log, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] All DeepSeek API endpoints failed. Last error: {last_error}\n")
        return None, None
            
    except Exception as e:
        print(f"DeepSeek API failed with error: {e}")
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        error_log = os.path.join(log_dir, f"error_log_{datetime.now().strftime('%Y%m%d')}.txt")
        with open(error_log, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] DeepSeek Exception: {str(e)}\n")
        return None, None

def call_gemini_api(messages):
    """Call the Google Gemini API with improved handling and formatting"""
    try:
        if not GEMINI_API_KEY:
            print("Gemini API key is missing.")
            return None, None
            
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            
            # Debug logging
            print(f"Using Gemini API with key: {GEMINI_API_KEY[:5]}...")
            
            # Try different models in case one is not available
            models_to_try = [
                GEMINI_MODEL,  # Main model (e.g., "gemini-2.0")
                "gemini-1.5-pro",  # Fallback model
                "gemini-pro"  # Legacy model as final fallback
            ]
            
            last_error = None
            for model_name in models_to_try:
                try:
                    print(f"Trying Gemini model: {model_name}")
                    
                    # Use the GenerativeModel directly
                    model = genai.GenerativeModel(model_name)
                    
                    # Convert our message format to Gemini format
                    gemini_messages = []
                    system_content = None
                    
                    # Extract system message first
                    for msg in messages:
                        if msg["role"] == "system":
                            system_content = msg["content"]
                            break
                    
                    # Format remaining messages
                    for msg in messages:
                        if msg["role"] == "user":
                            # Prepend system prompt to first user message if available
                            if system_content and len(gemini_messages) == 0:
                                content = f"{system_content}\n\nUser: {msg['content']}"
                                gemini_messages.append({"role": "user", "parts": [content]})
                                system_content = None  # Clear so we don't use it again
                            else:
                                gemini_messages.append({"role": "user", "parts": [msg["content"]]})
                        elif msg["role"] == "assistant":
                            gemini_messages.append({"role": "model", "parts": [msg["content"]]})
                    
                    # Debug logging
                    print(f"Sending to Gemini API, {len(gemini_messages)} messages")
                    
                    # Set safety settings to be more permissive for mental health discussions
                    safety_settings = [
                        {
                            "category": "HARM_CATEGORY_HARASSMENT",
                            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                        },
                        {
                            "category": "HARM_CATEGORY_HATE_SPEECH",
                            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                        },
                        {
                            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                        },
                        {
                            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                        }
                    ]
                    
                    try:
                        # Generate the content with safety settings if supported by the model
                        try:
                            response = model.generate_content(
                                gemini_messages,
                                safety_settings=safety_settings,
                                generation_config={"temperature": 0.7, "max_output_tokens": 2000}
                            )
                        except TypeError:
                            # If safety_settings not supported by this model version
                            response = model.generate_content(
                                gemini_messages,
                                generation_config={"temperature": 0.7, "max_output_tokens": 2000}
                            )
                        
                        if hasattr(response, 'text'):
                            return response.text, "gemini"
                        elif hasattr(response, 'parts'):
                            return response.parts[0].text, "gemini"
                        else:
                            print(f"Unexpected response format from Gemini: {response}")
                            last_error = "Unexpected response format"
                            continue  # Try the next model
                            
                    except Exception as api_err:
                        print(f"Gemini API call error with model {model_name}: {str(api_err)}")
                        last_error = api_err
                        continue  # Try the next model
                        
                except Exception as model_err:
                    print(f"Gemini model initialization error with {model_name}: {str(model_err)}")
                    last_error = model_err
                    continue  # Try the next model
            
            # If we get here, all models failed
            print(f"All Gemini API models failed. Last error: {last_error}")
            log_dir = os.path.join(os.path.dirname(__file__), "logs")
            os.makedirs(log_dir, exist_ok=True)
            error_log = os.path.join(log_dir, f"error_log_{datetime.now().strftime('%Y%m%d')}.txt")
            with open(error_log, "a") as f:
                f.write(f"[{datetime.now().isoformat()}] All Gemini API models failed. Last error: {str(last_error)}\n")
            return None, None
            
        except ImportError:
            print("Google AI module not installed. Please run: pip install google-generativeai>=0.3.0")
            return None, None
        
    except Exception as e:
        print(f"Gemini API failed with error: {e}")
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        error_log = os.path.join(log_dir, f"error_log_{datetime.now().strftime('%Y%m%d')}.txt")
        with open(error_log, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] Gemini Exception: {str(e)}\n")
        return None, None
    
def get_ai_response(messages, session_id):
    """Try each AI service in order until one succeeds, with improved error handling"""
    
    # Get the session to check for 5-minute rule
    session = sessions.get(session_id)
    if not session:
        return "Session not found. Please create a new session.", "error"
    
    # Calculate chat duration to determine if we should apply 5-minute rule
    is_first_5_minutes = False
    if session.get('chat_start_time'):
        try:
            chat_duration = datetime.now() - datetime.fromisoformat(session['chat_start_time'])
            is_first_5_minutes = chat_duration.total_seconds() < 300  # 5 minutes in seconds
            print(f"DEBUG: Chat duration: {chat_duration.total_seconds()} seconds. First 5 minutes: {is_first_5_minutes}")
        except Exception as e:
            print(f"Error parsing chat start time: {e}")
            is_first_5_minutes = False
    
    # Create a copy of messages to modify
    modified_messages = [msg.copy() if isinstance(msg, dict) else msg for msg in messages]
    
    # Apply 5-minute counselor rule if applicable
    if is_first_5_minutes:
        # Find the system message and modify it
        system_found = False
        for i, msg in enumerate(modified_messages):
            if isinstance(msg, dict) and msg.get("role") == "system":
                # Add instruction to avoid counselor references unless crisis
                modified_messages[i]["content"] += "\n\n## IMPORTANT TEMPORARY INSTRUCTION\nFor the first 5 minutes of this conversation, DO NOT suggest or refer the user to a counselor UNLESS they express crisis-level concerns (suicidal thoughts, self-harm, harm to others, or severe emotional distress). Focus on providing direct support and coping strategies yourself instead."
                system_found = True
                print("DEBUG: Added 5-minute instruction to system message")
                break
        
        if not system_found:
            print("DEBUG: No system message found to modify for 5-minute rule")
    
    # Apply topic extensions
    modified_messages = flask_implementation(session_id, modified_messages)
    
    # Verify that we have at least one API key before attempting to call APIs
    have_api_keys = any([QWEN_API_KEY, DEEPSEEK_API_KEY, GEMINI_API_KEY])
    if not have_api_keys:
        return "Sorry, the AI service is currently unavailable. Please check your API key configuration.", "error"
    
    # Detailed logging of API attempt sequence
    print(f"Starting API call sequence with keys: Qwen: {bool(QWEN_API_KEY)}, DeepSeek: {bool(DEEPSEEK_API_KEY)}, Gemini: {bool(GEMINI_API_KEY)}")
    
    # First try Qwen API (primary)
    if QWEN_API_KEY:
        print("Attempting to call Qwen API...")
        start_time = time.time()
        response, source = call_qwen_api(modified_messages)
        elapsed = time.time() - start_time
        if response:
            print(f"Successfully received response from Qwen API in {elapsed:.2f} seconds")
            return response, source
        print(f"Qwen API failed after {elapsed:.2f} seconds")
    else:
        print("Skipping Qwen API (no API key)")
    
    # Then try DeepSeek API (first fallback)
    if DEEPSEEK_API_KEY:
        print("Attempting to call DeepSeek API...")
        start_time = time.time()
        response, source = call_deepseek_api(modified_messages)
        elapsed = time.time() - start_time
        if response:
            print(f"Successfully received response from DeepSeek API in {elapsed:.2f} seconds")
            return response, source
        print(f"DeepSeek API failed after {elapsed:.2f} seconds")
    else:
        print("Skipping DeepSeek API (no API key)")
    
    # Finally try Gemini API (second fallback)
    if GEMINI_API_KEY:
        print("Attempting to call Gemini API...")
        start_time = time.time()
        response, source = call_gemini_api(modified_messages)
        elapsed = time.time() - start_time
        if response:
            print(f"Successfully received response from Gemini API in {elapsed:.2f} seconds")
            return response, source
        print(f"Gemini API failed after {elapsed:.2f} seconds")
    else:
        print("Skipping Gemini API (no API key)")
    
    # Log comprehensive error details
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    error_log = os.path.join(log_dir, f"api_failure_{datetime.now().strftime('%Y%m%d')}.txt")
    
    # Write detailed error log with message data for debugging
    with open(error_log, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] All API calls failed for session {session_id}\n")
        f.write(f"API keys available: Qwen: {bool(QWEN_API_KEY)}, DeepSeek: {bool(DEEPSEEK_API_KEY)}, Gemini: {bool(GEMINI_API_KEY)}\n")
        f.write("Message count: " + str(len(modified_messages)) + "\n")
        f.write("First few messages (truncated):\n")
        for i, msg in enumerate(modified_messages[:3]):  # First 3 messages only
            if isinstance(msg, dict):
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')[:100] + '...' if len(msg.get('content', '')) > 100 else msg.get('content', '')
                f.write(f"  Message {i}: Role={role}, Content={content}\n")
    
    # If all APIs failed, return an appropriate error message
    return "I'm sorry, I'm having connectivity issues right now. Please try again later. The server team has been notified of this issue.", "error"

# Log conversations to a file
def log_conversation(user_message, ai_message, model_used, conversation_id):
    try:
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # Create log entry
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "conversation_id": conversation_id,
            "user_message": user_message,
            "ai_message": ai_message,
            "model_used": model_used
        }
        
        try:
            log_file = os.path.join(log_dir, f"conversation_{datetime.now().strftime('%Y%m%d')}.json")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            # If file writing fails, print to stdout instead
            print(f"LOG: {json.dumps(log_entry, ensure_ascii=False)}")
            print(f"File writing error: {e}")
    except Exception as e:
        print(f"Error logging conversation: {e}")
        
# Function to initialize a new session
def initialize_session(session_id=None):
    if not session_id:
        session_id = str(uuid.uuid4())
    
    sessions[session_id] = {
        "conversation_id": session_id,
        "messages": [],
        "user_info": {
            "name": "",
            "concerns": [],
            "onboarded": False,
            "language": "English"
        },
        "chat_start_time": datetime.now().isoformat(),
        "applied_extensions": [],
        "extension_applied_at": None,
        "show_therapist_options": False,
        "last_appointment": None
    }
    
    return session_id

# API endpoints
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint to verify the API is running"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "qwen": bool(QWEN_API_KEY),
            "deepseek": bool(DEEPSEEK_API_KEY),
            "gemini": bool(GEMINI_API_KEY),
            "mock_mode": MOCK_API_MODE
        },
        "prompt_loaded": bool(SYSTEM_PROMPT),
        "extensions_available": {
            topic: bool(load_extension(topic)) 
            for topic in TOPIC_KEYWORDS.keys()
        }
    })

@app.route('/api/session/new', methods=['POST'])
def create_session():
    """Create a new session for a user"""
    try:
        session_id = initialize_session()
        
        # Log session creation
        print(f"Created new session: {session_id}")
        
        return jsonify({
            "status": "success",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error creating session: {e}")
        return jsonify({
            "status": "error",
            "error": f"Failed to create session: {str(e)}"
        }), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """Process a chat message and return a response"""
    try:
        data = request.json
        
        # Debug logging
        print(f"Received chat request: {data}")
        
        # Validate required fields
        if not data or 'message' not in data or 'session_id' not in data:
            print("Missing required fields in chat request")
            return jsonify({
                "status": "error",
                "error": "Missing required fields: message and session_id"
            }), 400
        
        session_id = data['session_id']
        user_message = data['message']
        
        print(f"Processing chat for session {session_id}: {user_message[:50]}...")
        
        # Check if session exists
        if session_id not in sessions:
            print(f"Session {session_id} not found")
            # Auto-create the session if it doesn't exist for robustness
            initialize_session(session_id)
            print(f"Auto-created session {session_id}")
        
        # Get the session
        session = sessions[session_id]
        
        # Initialize chat_start_time if not already set
        if 'chat_start_time' not in session:
            session['chat_start_time'] = datetime.now().isoformat()
            
        # Check for therapist request
        is_therapist_request = detect_therapist_request(user_message)
        if is_therapist_request:
            session['show_therapist_options'] = True
            print(f"Therapist request detected in session {session_id}")
            
        # Construct messages for AI
        if not session.get('messages'):
            # First message - include system prompt
            session['messages'] = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ]
        else:
            # Add user message to existing conversation
            session['messages'].append({"role": "user", "content": user_message})
            
        # Get AI response
        print(f"Getting AI response for session {session_id}")
        ai_message, model_used = get_ai_response(session['messages'], session_id)
        
        # Add AI response to session messages
        session['messages'].append({"role": "assistant", "content": ai_message})
        
        # Log the conversation
        log_conversation(user_message, ai_message, model_used, session_id)
        
        # Check if therapist keyword is in AI response
        if any(keyword in ai_message.lower() for keyword in ["therapist", "counselor", "professional help"]):
            session['show_therapist_options'] = True
            print(f"Therapist mention detected in AI response, session {session_id}")
        
        # Prepare response
        response = {
            "status": "success",
            "message": ai_message,
            "model_used": model_used,
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id
        }
        
        # Add therapist options if requested
        if session.get('show_therapist_options', False):
            response["show_therapist_options"] = True
            
        print(f"Sending chat response for session {session_id}")
        return jsonify(response)
        
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        # Log the error
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        error_log = os.path.join(log_dir, f"error_log_{datetime.now().strftime('%Y%m%d')}.txt")
        with open(error_log, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] Chat endpoint error: {str(e)}\n")
            
        return jsonify({
            "status": "error",
            "error": f"An unexpected error occurred: {str(e)}. Please try again."
        }), 500

@app.route('/api/conversations/<session_id>', methods=['GET'])
def get_conversation(session_id):
    """Get the conversation history for a session"""
    if session_id not in sessions:
        return jsonify({
            "status": "error",
            "error": "Session not found"
        }), 404
        
    session = sessions[session_id]
    
    # Return only user and assistant messages (no system messages)
    messages = [msg for msg in session.get('messages', []) 
               if msg.get('role') in ('user', 'assistant')]
    
    return jsonify({
        "status": "success",
        "session_id": session_id,
        "messages": messages,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """Submit user feedback about the conversation"""
    try:
        data = request.json
        
        # Validate required fields
        if not data or 'session_id' not in data or 'rating' not in data:
            return jsonify({
                "status": "error",
                "error": "Missing required fields: session_id and rating"
            }), 400
            
        session_id = data['session_id']
        rating = data['rating']
        feedback_text = data.get('feedback', '')
        
        # Check if session exists
        if session_id not in sessions:
            return jsonify({
                "status": "error",
                "error": "Session not found"
            }), 404
            
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # Log the feedback
        feedback_log = os.path.join(log_dir, f"feedback_{datetime.now().strftime('%Y%m%d')}.json")
        feedback_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "rating": rating,
            "feedback": feedback_text
        }
        
        with open(feedback_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback_entry, ensure_ascii=False) + "\n")
            
        return jsonify({
            "status": "success",
            "message": "Feedback submitted successfully"
        })
        
    except Exception as e:
        print(f"Error in feedback endpoint: {e}")
        return jsonify({
            "status": "error",
            "error": "An unexpected error occurred"
        }), 500

@app.route('/api/session/<session_id>/clear', methods=['POST'])
def clear_session(session_id):
    """Clear a session's conversation history but keep the session alive"""
    if session_id not in sessions:
        return jsonify({
            "status": "error",
            "error": "Session not found"
        }), 404
        
    # Reset messages but keep user info
    session = sessions[session_id]
    user_info = session.get('user_info', {})
    
    # Re-initialize session with same ID
    initialize_session(session_id)
    
    # Restore user info
    sessions[session_id]['user_info'] = user_info
    
    return jsonify({
        "status": "success",
        "message": "Session cleared successfully",
        "session_id": session_id
    })

@app.route('/api/status', methods=['GET'])
def api_status():
    """Extended status endpoint with more detailed information"""
    # Count active sessions (sessions with messages)
    active_sessions = sum(1 for s in sessions.values() if s.get('messages'))
    
    # Check extensions directory
    base_path = os.path.dirname(os.path.abspath(__file__))
    extensions_dir = os.path.join(base_path, "extensions")
    extension_status = {}
    
    if os.path.exists(extensions_dir):
        for topic in TOPIC_KEYWORDS.keys():
            extension_path = os.path.join(extensions_dir, f"{topic}_extension.md")
            extension_status[topic] = os.path.exists(extension_path)
    
    # Check for prompt file
    prompt_path = os.path.join(base_path, "lumonmind_prompt.md")
    prompt_exists = os.path.exists(prompt_path)
    
    return jsonify({
        "status": "operational",
        "version": "1.0.0",  # Update with your actual version
        "timestamp": datetime.now().isoformat(),
        "uptime": time.time() - app.start_time if hasattr(app, 'start_time') else 0,
        "active_sessions": active_sessions,
        "total_sessions": len(sessions),
        "api_services": {
            "qwen": "available" if QWEN_API_KEY else "unavailable",
            "deepseek": "available" if DEEPSEEK_API_KEY else "unavailable",
            "gemini": "available" if GEMINI_API_KEY else "unavailable",
            "mock_mode": MOCK_API_MODE
        },
        "system_prompt": {
            "loaded": bool(SYSTEM_PROMPT),
            "file_exists": prompt_exists,
            "length": len(SYSTEM_PROMPT) if SYSTEM_PROMPT else 0
        },
        "extensions": extension_status
    })
    
@app.route('/api/session/<session_id>/onboard', methods=['POST'])
def onboard_user(session_id):
    """Set up user information after onboarding"""
    try:
        # Debug logging
        print(f"Received onboarding request for session: {session_id}")
        
        # Verify that the session exists
        if session_id not in sessions:
            print(f"Session {session_id} not found during onboarding")
            # Auto-create the session for robustness
            initialize_session(session_id)
            print(f"Auto-created session {session_id} during onboarding")
            
        # Get request data
        data = request.json
        if not data:
            print("No request data in onboarding request")
            return jsonify({
                "status": "error",
                "message": "Missing request data"
            }), 400
            
        if 'name' not in data:
            print("Missing name in onboarding request")
            return jsonify({
                "status": "error",
                "message": "Missing required field: name"
            }), 400
            
        # Debug
        print(f"Onboarding user '{data.get('name')}' with language '{data.get('language', 'English')}'")
            
        # Update session with user info
        session = sessions[session_id]
        session['user_info']['name'] = data.get('name', '')
        session['user_info']['language'] = data.get('language', 'English')
        session['user_info']['onboarded'] = True
        
        # Start chat timer
        session['chat_start_time'] = datetime.now().isoformat()
        
        # Create a personalized greeting
        greeting = f"Hi {session['user_info']['name']}, I'm LumonMind, your AI mental health companion. How are you feeling today?"
        
        # If language is Hindi, provide a Hindi greeting as well
        if session['user_info']['language'] == 'Hindi':
            greeting += "\n\nNamaste! Aap kaise feel kar rahe hain aaj?"
            
        # Add initial messages to the conversation
        session['messages'] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "assistant", "content": greeting}
        ]
        
        print(f"Onboarding completed for session {session_id}")
        return jsonify({
            "status": "success",
            "greeting": greeting
        })
        
    except Exception as e:
        print(f"Error in onboard_user: {e}")
        return jsonify({
            "status": "error",
            "message": f"An error occurred during onboarding: {str(e)}"
        }), 500

@app.route('/api/session/<session_id>/chat', methods=['POST'])
def session_chat(session_id):
    """Process a chat message within a specific session"""
    try:
        # Verify session exists
        if session_id not in sessions:
            return jsonify({
                "status": "error",
                "code": "SESSION_NOT_FOUND",
                "message": "Session not found"
            }), 404
            
        # Get session and check if user is onboarded
        session = sessions[session_id]
        if not session.get('user_info', {}).get('onboarded', False):
            return jsonify({
                "status": "error",
                "code": "NOT_ONBOARDED",
                "message": "User not onboarded"
            }), 400
            
        # Get user message
        data = request.json
        if not data or 'message' not in data:
            return jsonify({
                "status": "error",
                "message": "No message provided"
            }), 400
            
        user_message = data['message']
        
        # Check for therapist request
        is_therapist_request = detect_therapist_request(user_message)
        if is_therapist_request:
            session['show_therapist_options'] = True
            
            return jsonify({
                "status": "success",
                "is_therapist_request": True,
                "response": "I understand you'd like to speak with a therapist. Let me help you book an appointment."
            })
            
        # Add user message to conversation
        if not session.get('messages'):
            # Initialize with system prompt if empty
            session['messages'] = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]
            
        # Add the user message
        session['messages'].append({"role": "user", "content": user_message})
        
        # Get AI response
        ai_message, model_used = get_ai_response(session['messages'], session_id)
        
        # Add AI response to conversation
        session['messages'].append({"role": "assistant", "content": ai_message})
        
        # Log the conversation
        log_conversation(user_message, ai_message, model_used, session_id)
        
        # Check if therapist options should be shown based on AI response
        therapist_mention = any(keyword in ai_message.lower() for keyword in ["therapist", "counselor", "professional help"])
        if therapist_mention:
            session['show_therapist_options'] = True
            
        return jsonify({
            "status": "success",
            "response": ai_message,
            "model_used": model_used,
            "is_therapist_request": session.get('show_therapist_options', False)
        })
        
    except Exception as e:
        print(f"Error in session_chat: {e}")
        return jsonify({
            "status": "error",
            "message": "An error occurred processing your message"
        }), 500

@app.route('/api/session/<session_id>/end', methods=['POST'])
def end_session_chat(session_id):
    """End the current chat but keep the session alive"""
    try:
        # Verify session exists
        if session_id not in sessions:
            return jsonify({
                "status": "error",
                "message": "Session not found"
            }), 404
            
        # Get session
        session = sessions[session_id]
        
        # Keep user info but reset messages
        user_info = session.get('user_info', {})
        user_name = user_info.get('name', '')
        
        # Reset messages
        session['messages'] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        
        # Reset chat start time
        session['chat_start_time'] = datetime.now().isoformat()
        
        # Reset therapist options
        session['show_therapist_options'] = False
        
        # Create greeting
        greeting = f"Hi {user_name}, I'm starting a new conversation. How can I help you today?"
        
        # Add assistant greeting
        session['messages'].append({"role": "assistant", "content": greeting})
        
        return jsonify({
            "status": "success",
            "greeting": greeting
        })
        
    except Exception as e:
        print(f"Error in end_session_chat: {e}")
        return jsonify({
            "status": "error",
            "message": "An error occurred ending the chat"
        }), 500

@app.route('/api/session/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a session completely"""
    try:
        # Verify session exists
        if session_id not in sessions:
            return jsonify({
                "status": "error",
                "message": "Session not found"
            }), 404
            
        # Delete the session
        del sessions[session_id]
        
        return jsonify({
            "status": "success",
            "message": "Session deleted successfully"
        })
        
    except Exception as e:
        print(f"Error in delete_session: {e}")
        return jsonify({
            "status": "error",
            "message": "An error occurred deleting the session"
        }), 500
        
@app.route('/api/session/<session_id>/therapist', methods=['POST'])
def book_therapist(session_id):
    """Handle therapist booking requests"""
    try:
        # Verify session exists
        if session_id not in sessions:
            return jsonify({
                "status": "error",
                "message": "Session not found"
            }), 404
            
        # Get booking details
        data = request.json
        if not data:
            return jsonify({
                "status": "error",
                "message": "No booking details provided"
            }), 400
            
        # Required fields
        required_fields = ['name', 'email', 'phone', 'appointment_date', 
                          'appointment_time', 'selectedTherapist', 'appointment_type']
        
        # Check for missing fields
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({
                "status": "error",
                "message": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400
            
        # Get session
        session = sessions[session_id]
        
        # Store appointment in session
        session['last_appointment'] = {
            "therapist": data.get('selectedTherapist'),
            "date": data.get('appointment_date'),
            "time": data.get('appointment_time'),
            "type": data.get('appointment_type'),
            "booked_at": datetime.now().isoformat()
        }
        
        # Log the appointment
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        appointment_log = os.path.join(log_dir, f"appointments_{datetime.now().strftime('%Y%m%d')}.json")
        with open(appointment_log, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id,
                "appointment": session['last_appointment'],
                "user_details": {
                    "name": data.get('name'),
                    "email": data.get('email'),
                    "phone": data.get('phone')
                }
            }, ensure_ascii=False) + "\n")
            
        # Create confirmation message
        confirmation_message = f"""Your appointment has been scheduled successfully!

Therapist: {data.get('selectedTherapist')}
Date: {data.get('appointment_date')}
Time: {data.get('appointment_time')}
Type: {data.get('appointment_type')} Session

We'll send a confirmation to {data.get('email')} with further details. You'll receive a reminder 24 hours before your appointment.

Thank you for taking this important step for your mental health."""

        return jsonify({
            "status": "success",
            "confirmation_message": confirmation_message
        })
        
    except Exception as e:
        print(f"Error in book_therapist: {e}")
        return jsonify({
            "status": "error",
            "message": "An error occurred booking your appointment"
        }), 500
        
# Main entry point
if __name__ == "__main__":
    # Verify API keys at startup
    qwen_key, deepseek_key, gemini_key = verify_api_keys()
    
    # Check if at least one API key is valid
    if not any([qwen_key, deepseek_key, gemini_key]):
        print("WARNING: No valid API keys found. The application may not function correctly.")

    
    # Record start time for uptime tracking
    app.start_time = time.time()
    
    # Get port from environment or use default
    port = int(os.getenv('PORT', 5000))
    
    # Set debug mode from environment
    debug_mode = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # Create necessary directories
    # Create static directory for html files if it doesn't exist
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)
        print(f"Created static directory at {static_dir}")
        
        # Copy index.html to static directory if it exists in the same directory as this script
        src_html = os.path.join(os.path.dirname(__file__), "index.html")
        if os.path.exists(src_html):
            import shutil
            dst_html = os.path.join(static_dir, "index.html")
            shutil.copy(src_html, dst_html)
            print(f"Copied index.html to {dst_html}")
    
    # Log startup information
    print(f"Starting LumonMind API on port {port}")
    print(f"Debug mode: {debug_mode}")
    
    if MOCK_API_MODE:
        print("RUNNING IN MOCK API MODE - No real AI services will be used")
    else:
        print(f"Available services: Qwen: {'Yes' if QWEN_API_KEY else 'No'}, "
              f"DeepSeek: {'Yes' if DEEPSEEK_API_KEY else 'No'}, "
              f"Gemini: {'Yes' if GEMINI_API_KEY else 'No'}")
    
    # Print URL for accessing the application
    print(f"\nApplication available at: http://localhost:{port}/")
    print(f"API endpoints available at: http://localhost:{port}/api/")
    
    # Start the Flask application
    app.run(host='0.0.0.0', port=port, debug=debug_mode)