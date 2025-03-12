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

# Constants
DEEPSEEK_MODEL = "deepseek-chat"
QWEN_MODEL = "qwen-max"
GEMINI_MODEL = "gemini-1.5-pro-latest"

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

# Enhanced API key handling with multiple fallback mechanisms
def get_api_key(provider="qwen"):
    """
    Get the API key from various sources in the following priority order:
    1. Environment variable
    
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
            return api_key
    
    # No API key found
    return None

# Get API keys with the function
DEEPSEEK_API_KEY = get_api_key("deepseek")
QWEN_API_KEY = get_api_key("qwen")
GEMINI_API_KEY = get_api_key("gemini")

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
                    sys.exit(1)
                return prompt_content
        else:
            # If we reach this point, no prompt source was found
            print("CRITICAL ERROR: Cannot find prompt template file.")
            print("The application requires the lumonmind_prompt.md file to function.")
            sys.exit(1)
    except Exception as e:
        print(f"CRITICAL ERROR: Cannot load prompt template: {e}")
        print("The application requires the lumonmind_prompt.md file to function.")
        sys.exit(1)

# This will exit the application if the prompt cannot be loaded
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

# Helper functions for API calls
def call_qwen_api(messages):
    """Call the Qwen API through Aliyun Dashscope using OpenAI client"""
    try:
        if not QWEN_API_KEY:
            print("Qwen API key is missing.")
            return None, None
            
        # Use OpenAI client with Aliyun's DashScope endpoint
        try:
            from openai import OpenAI
            
            client = OpenAI(
                api_key=QWEN_API_KEY,
                base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
            )
            
            # Print API key (first few characters for debugging)
            print(f"Using Qwen API key: {QWEN_API_KEY[:5]}...")
            
            try:
                completion = client.chat.completions.create(
                    model=QWEN_MODEL,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2000,
                    timeout=30
                )
                
                # Extract content from response
                content = completion.choices[0].message.content
                return content, "qwen"
                
            except Exception as e:
                print(f"Qwen API Error: {str(e)}")
                # Log the error
                log_dir = os.path.join(os.path.dirname(__file__), "logs")
                os.makedirs(log_dir, exist_ok=True)
                error_log = os.path.join(log_dir, f"error_log_{datetime.now().strftime('%Y%m%d')}.txt")
                with open(error_log, "a") as f:
                    f.write(f"[{datetime.now().isoformat()}] Qwen API Error: {str(e)}\n")
                return None, None
        except ImportError:
            print("OpenAI module not installed. Please run: pip install openai")
            return None, None
            
    except Exception as e:
        print(f"Qwen API failed with error: {e}")
        # Log the error
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        error_log = os.path.join(log_dir, f"error_log_{datetime.now().strftime('%Y%m%d')}.txt")
        with open(error_log, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] Qwen Exception: {str(e)}\n")
        return None, None

def call_deepseek_api(messages):
    """Call the DeepSeek API with fallback support"""
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
        
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        # Print the endpoint URL
        endpoint_url = "https://api.deepseek.com/v1/chat/completions"
        print(f"Calling DeepSeek API at: {endpoint_url}")
        
        response = requests.post(
            endpoint_url,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"DeepSeek API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            response_json = response.json()
            print(f"DeepSeek API Response: {response_json}")
            return response_json["choices"][0]["message"]["content"], "deepseek"
        else:
            print(f"DeepSeek API Error: {response.text}")
            # Log the error
            log_dir = os.path.join(os.path.dirname(__file__), "logs")
            os.makedirs(log_dir, exist_ok=True)
            error_log = os.path.join(log_dir, f"error_log_{datetime.now().strftime('%Y%m%d')}.txt")
            with open(error_log, "a") as f:
                f.write(f"[{datetime.now().isoformat()}] DeepSeek API Error: {response.text}\nHeaders: {headers}\nPayload: {payload}\n")
            return None, None
            
    except Exception as e:
        print(f"DeepSeek API failed with error: {e}")
        # Log the error
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        error_log = os.path.join(log_dir, f"error_log_{datetime.now().strftime('%Y%m%d')}.txt")
        with open(error_log, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] DeepSeek Exception: {str(e)}\n")
        return None, None

def call_gemini_api(messages):
    """Call the Google Gemini API"""
    try:
        if not GEMINI_API_KEY:
            print("Gemini API key is missing.")
            return None, None
            
        # Try to import and configure genai
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel(GEMINI_MODEL)
            
            # Convert our message format to Gemini format
            gemini_messages = []
            system_added = False
            
            for msg in messages:
                if msg["role"] == "system":
                    # For Gemini, we'll add system prompt to the first user message
                    system_added = True
                    continue
                elif msg["role"] == "user":
                    if not system_added and len(gemini_messages) == 0:
                        # Add system prompt to first user message
                        gemini_messages.append({"role": "user", "parts": [SYSTEM_PROMPT + "\n\nUser: " + msg["content"]]})
                        system_added = True
                    else:
                        gemini_messages.append({"role": "user", "parts": [msg["content"]]})
                elif msg["role"] == "assistant":
                    gemini_messages.append({"role": "model", "parts": [msg["content"]]})
            
            response = model.generate_content(gemini_messages)
            return response.text, "gemini"
        except ImportError:
            print("Google AI module not installed. Please run: pip install google-generativeai")
            return None, None
        
    except Exception as e:
        print(f"Gemini API failed with error: {e}")
        # Log the error
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        error_log = os.path.join(log_dir, f"error_log_{datetime.now().strftime('%Y%m%d')}.txt")
        with open(error_log, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] Gemini Exception: {str(e)}\n")
        return None, None

def get_ai_response(messages, session_id):
    """Try each AI service in order until one succeeds, with all modifications applied"""
    
    # Get the session to check for 5-minute rule
    session = sessions.get(session_id)
    if not session:
        return "Session not found. Please create a new session.", "error"
    
    # Calculate chat duration to determine if we should apply 5-minute rule
    is_first_5_minutes = False
    if session.get('chat_start_time'):
        chat_duration = datetime.now() - datetime.fromisoformat(session['chat_start_time'])
        is_first_5_minutes = chat_duration.total_seconds() < 300  # 5 minutes in seconds
        print(f"DEBUG: Chat duration: {chat_duration.total_seconds()} seconds. First 5 minutes: {is_first_5_minutes}")
    
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
    
    # First try Qwen
    response, source = call_qwen_api(modified_messages)
    if response:
        return response, source
    
    # Then try DeepSeek
    response, source = call_deepseek_api(modified_messages)
    if response:
        return response, source
    
    # Finally try Gemini
    response, source = call_gemini_api(modified_messages)
    if response:
        return response, source
    
    # If all fail, return an error message
    return "I'm sorry, I'm having connectivity issues right now. Please try again later. Make sure your API keys are correct in the .env file.", "error"

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
            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            # If file writing fails, print to stdout instead
            print(f"LOG: {json.dumps(log_entry)}")
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
        "chat_start_time": None,
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
            "gemini": bool(GEMINI_API_KEY)
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
    session_id = initialize_session()
    
    return jsonify({
        "status": "success",
        "session_id": session_id,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/session/<session_id>/onboard', methods=['POST'])
def onboard_user(session_id):
    """Onboard a new user with their information"""
    if session_id not in sessions:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400
    
    # Extract user information
    name = data.get('name', '')
    language_preference = data.get('language', 'English')
    
    if not name:
        return jsonify({"status": "error", "message": "Name is required"}), 400
    
    # Update session with user information - simplified without concerns
    sessions[session_id]['user_info']['name'] = name
    sessions[session_id]['user_info']['concerns'] = []  # Empty list as we're not collecting concerns
    sessions[session_id]['user_info']['language'] = language_preference
    sessions[session_id]['user_info']['onboarded'] = True
    
    # Create initial system message
    system_message = SYSTEM_PROMPT
    
    # Add user info to the system message (simplified without concerns)
    system_message += f"\n\nThe user's name is {name}."
        
    # Add language preference
    system_message += f"\n\nThe user's preferred language is {language_preference}."
    
    # Add system message to the conversation
    sessions[session_id]['messages'].append({"role": "system", "content": system_message})
    
    # Set chat start time when user completes onboarding
    sessions[session_id]['chat_start_time'] = datetime.now().isoformat()
    print(f"DEBUG: Chat start time set during onboarding: {sessions[session_id]['chat_start_time']}")
    
    # Add welcome message from assistant
    greeting = f"Hello {name}! I'm here to support you with your mental health journey. How are you feeling today?"
    sessions[session_id]['messages'].append({"role": "assistant", "content": greeting})
    
    return jsonify({
        "status": "success",
        "session_id": session_id,
        "greeting": greeting,
        "user_info": sessions[session_id]['user_info']
    })

@app.route('/api/session/<session_id>/chat', methods=['POST'])
def chat(session_id):
    """Process a chat message from the user"""
    if session_id not in sessions:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    
    data = request.json
    if not data or 'message' not in data:
        return jsonify({"status": "error", "message": "No message provided"}), 400
    
    user_message = data['message']
    session = sessions[session_id]
    
    # Check if the user is onboarded
    if not session['user_info']['onboarded'] and 'skip_onboarding' not in data:
        return jsonify({
            "status": "error", 
            "message": "User not onboarded",
            "code": "NOT_ONBOARDED"
        }), 400
    
    # Set chat start time if this is the first message
    if not session.get('chat_start_time'):
        session['chat_start_time'] = datetime.now().isoformat()
        print(f"DEBUG: Chat start time set on first message: {session['chat_start_time']}")
    
    # Check if this is a therapist request
    is_therapist_request = detect_therapist_request(user_message)
    
    # Add user message to chat history with timestamp
    session['messages'].append({
        "role": "user", 
        "content": user_message,
        "timestamp": datetime.now().isoformat()
    })
    
    if is_therapist_request:
        # Return special response for therapist requests
        response = {
            "status": "success",
            "is_therapist_request": True,
            "message": "I understand you'd like to book an appointment with a human therapist. Let me help you with that."
        }
        
        # Add assistant acknowledgment to the conversation
        acknowledgment = "I understand you'd like to book an appointment with a human therapist. Let me help you with that:"
        session['messages'].append({"role": "assistant", "content": acknowledgment})
        
        return jsonify(response)
    
    # Prepare messages for AI API
    api_messages = [msg for msg in session['messages']]
    
    # Get AI response
    ai_response, model_used = get_ai_response(api_messages, session_id)
    
    # Add assistant response to chat history
    session['messages'].append({"role": "assistant", "content": ai_response})
    
    # Log the conversation
    log_conversation(user_message, ai_response, model_used, session_id)
    
    return jsonify({
        "status": "success",
        "is_therapist_request": False,
        "response": ai_response,
        "model_used": model_used,
        "applied_extensions": session.get('applied_extensions', [])
    })
    
@app.route('/api/session/<session_id>/therapist', methods=['POST'])
def book_therapist(session_id):
    """Book a therapist appointment"""
    if session_id not in sessions:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400
    
    # Required fields validation
    required_fields = ['name', 'email', 'phone', 'appointment_date', 
                      'appointment_time', 'appointment_type']
    
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({
            "status": "error", 
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }), 400
    
    # Email validation (simple)
    email = data.get('email')
    if not email or "@" not in email or "." not in email:
        return jsonify({
            "status": "error", 
            "message": "Please enter a valid email address"
        }), 400
    
    # Phone validation (simple)
    phone = data.get('phone')
    if not phone or not any(c.isdigit() for c in phone) or sum(c.isdigit() for c in phone) < 10:
        return jsonify({
            "status": "error", 
            "message": "Please enter a valid phone number with at least 10 digits"
        }), 400
    
    # Store appointment details
    appointment = {
        "name": data.get('name'),
        "email": data.get('email'),
        "phone": data.get('phone'),
        "date": data.get('appointment_date'),
        "time": data.get('appointment_time'),
        "type": data.get('appointment_type'),
        "specialty": data.get('specialty', []),
        "gender_preference": data.get('gender_preference', 'No Preference'),
        "reason": data.get('reason', ''),
        "booked_at": datetime.now().isoformat()
    }
    
    # Store in session
    sessions[session_id]['last_appointment'] = appointment
    
    # Add a message to the chat about the booking
    confirmation_message = f"I've scheduled your appointment for {appointment['date']} at {appointment['time']}. A confirmation email will be sent to {appointment['email']}. Is there anything else I can help you with in the meantime?"
    sessions[session_id]['messages'].append({"role": "assistant", "content": confirmation_message})
    
    # Here you would typically send this data to your backend or database
    
    # Log the appointment booking
    try:
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "appointment": appointment
        }
        
        try:
            log_file = os.path.join(log_dir, f"appointments_{datetime.now().strftime('%Y%m%d')}.json")
            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            print(f"LOG: {json.dumps(log_entry)}")
            print(f"File writing error: {e}")
    except Exception as e:
        print(f"Error logging appointment: {e}")
    
    return jsonify({
        "status": "success",
        "appointment": appointment,
        "confirmation_message": confirmation_message
    })

@app.route('/api/session/<session_id>/history', methods=['GET'])
def get_chat_history(session_id):
    """Get the chat history for a session"""
    if session_id not in sessions:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    
    session = sessions[session_id]
    
    # Filter out system messages
    chat_messages = [msg for msg in session['messages'] if msg['role'] != 'system']
    
    return jsonify({
        "status": "success",
        "session_id": session_id,
        "user_info": session['user_info'],
        "messages": chat_messages,
        "applied_extensions": session.get('applied_extensions', [])
    })

@app.route('/api/session/<session_id>/end', methods=['POST'])
def end_session(session_id):
    """End the current conversation but keep the session"""
    if session_id not in sessions:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    
    session = sessions[session_id]
    
    # Keep user info but reset messages
    user_info = session['user_info']
    
    # Reset messages
    session['messages'] = []
    
    # Re-add system message with user info
    system_message = SYSTEM_PROMPT
    system_message += f"\n\nThe user's name is {user_info['name']}."
    
    # Add language preference
    system_message += f"\n\nThe user's preferred language is {user_info['language']}."
    
    session['messages'].append({"role": "system", "content": system_message})
    
    # Reset chat start time for the new conversation
    session['chat_start_time'] = datetime.now().isoformat()
    print(f"DEBUG: Chat start time reset on new conversation: {session['chat_start_time']}")
    
    # Reset applied extensions
    session['applied_extensions'] = []
    session['extension_applied_at'] = None
    
    # Add welcome message
    greeting = f"Hello {user_info['name']}! I'm here to continue supporting you. How are you feeling today?"
    session['messages'].append({"role": "assistant", "content": greeting})
    
    return jsonify({
        "status": "success",
        "session_id": session_id,
        "greeting": greeting
    })

@app.route('/api/session/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a session completely"""
    if session_id not in sessions:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    
    # Remove the session
    del sessions[session_id]
    
    return jsonify({
        "status": "success",
        "message": "Session deleted successfully"
    })

@app.route('/api/extensions', methods=['GET'])
def list_extensions():
    """List all available topic extensions"""
    extensions = {}
    
    for topic in TOPIC_KEYWORDS.keys():
        extension_content = load_extension(topic)
        extensions[topic] = bool(extension_content)
    
    return jsonify({
        "status": "success",
        "available_extensions": extensions
    })

@app.route('/api/session/<session_id>/info', methods=['GET'])
def get_session_info(session_id):
    """Get detailed information about a session"""
    if session_id not in sessions:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    
    session = sessions[session_id]
    
    # Prepare session info with privacy considerations
    session_info = {
        "session_id": session_id,
        "created_at": session.get('created_at', 'unknown'),
        "user_info": {
            "name": session['user_info']['name'],
            "language": session['user_info']['language'],
            "onboarded": session['user_info']['onboarded']
        },
        "message_count": len([msg for msg in session['messages'] if msg['role'] != 'system']),
        "applied_extensions": session.get('applied_extensions', []),
        "has_appointments": bool(session.get('last_appointment'))
    }
    
    # Calculate session duration if we have a chat start time
    if session.get('chat_start_time'):
        try:
            start_time = datetime.fromisoformat(session['chat_start_time'])
            duration = datetime.now() - start_time
            session_info['session_duration_seconds'] = duration.total_seconds()
        except:
            session_info['session_duration_seconds'] = 'unknown'
    
    return jsonify({
        "status": "success",
        "session_info": session_info
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({"status": "error", "message": "Internal server error"}), 500

if __name__ == "__main__":
    # Make sure logs directory exists
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Create extensions directory if it doesn't exist
    extensions_dir = os.path.join(os.path.dirname(__file__), "extensions")
    os.makedirs(extensions_dir, exist_ok=True)
    
    # Start the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)
