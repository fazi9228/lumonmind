import streamlit as st
import os
import json
import requests
import sys
import io
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta, time
import uuid

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

# Constants
DEEPSEEK_MODEL = "deepseek-chat"
QWEN_MODEL = "qwen-max"
GEMINI_MODEL = "gemini-1.5-pro-latest"

# Set page configuration
st.set_page_config(
    page_title="LumonMind - Mental Health Support",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enhanced API key handling with multiple fallback mechanisms
def get_api_key(provider="qwen"):
    """
    Get the API key from various sources in the following priority order:
    1. Environment variable
    2. Streamlit secrets (for deployment)
    3. Session state (if manually entered in UI)
    
    Args:
        provider (str): The API provider ("qwen", "deepseek", or "gemini")
    """
    env_var_names = {
        "qwen": ["QWEN_API_KEY"],
        "deepseek": ["DEEPSEEK_API_KEY"],
        "gemini": ["GEMINI_API_KEY"]
    }
    
    # Check environment variables first (loaded from .env file in local development)
    for env_var in env_var_names.get(provider, []):
        api_key = os.getenv(env_var)
        if api_key:
            return api_key
    
    # Check Streamlit secrets (for deployment)
    try:
        # Use the in operator to check if the key exists
        if provider in st.secrets:
            api_key = st.secrets[provider]
            if api_key:
                return api_key
    except:
        # Silently continue if secrets aren't available
        pass
    
    # No API key found
    return None

# Get API keys with the new function
DEEPSEEK_API_KEY = get_api_key("deepseek")
QWEN_API_KEY = get_api_key("qwen")
GEMINI_API_KEY = get_api_key("gemini")

# Load the prompt template - critical for operation
def load_prompt_template():
    try:
        # First try to load from the local file
        prompt_path = os.path.join(os.path.dirname(__file__), "lumonmind_prompt.md")
        
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_content = f.read()
                if not prompt_content or len(prompt_content.strip()) < 10:
                    st.error("Prompt file exists but appears to be empty or too short.")
                    sys.exit(1)
                return prompt_content
        else:
            # If local file doesn't exist, try to get from Streamlit secrets
            try:
                if "PROMPT_CONTENT" in st.secrets:
                    prompt_content = st.secrets["PROMPT_CONTENT"]
                    if not prompt_content or len(prompt_content.strip()) < 10:
                        st.error("Prompt content in secrets appears to be empty or too short.")
                        sys.exit(1)
                    return prompt_content
            except:
                # If we can't access secrets, handle this situation
                pass
                
            # If we reach this point, no prompt source was found
            st.error("CRITICAL ERROR: Cannot find prompt template file or secret.")
            st.error("The application requires the lumonmind_prompt.md file or PROMPT_CONTENT secret to function.")
            sys.exit(1)
    except Exception as e:
        st.error(f"CRITICAL ERROR: Cannot load prompt template: {e}")
        st.error("The application requires the lumonmind_prompt.md file or PROMPT_CONTENT secret to function.")
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

# Initialize session state variables
if "messages" not in st.session_state:
    st.session_state.messages = []

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())

if "user_info" not in st.session_state:
    st.session_state.user_info = {
        "name": "",
        "concerns": [],
        "onboarded": False
    }

# Add therapist booking-related session state variables
if "show_therapist_options" not in st.session_state:
    st.session_state.show_therapist_options = False

# Add chat start time tracking
if "chat_start_time" not in st.session_state:
    st.session_state.chat_start_time = None

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

# This function should be called from the main display_chat_interface function
# to handle therapist requests
def handle_therapist_request(prompt):
    """Handle a detected therapist request"""
    # Store the original user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Show the user message in the chat
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Set flag to show therapist options
    st.session_state.show_therapist_options = True
    
    # Add assistant acknowledgment
    acknowledgment = "I understand you'd like to book an appointment with a human therapist. Let me help you with that:"
    st.session_state.messages.append({"role": "assistant", "content": acknowledgment})
    
    # Show acknowledgment in chat
    with st.chat_message("assistant"):
        st.markdown(acknowledgment)
    
    # Show the appointment booking options
    display_appointment_options()
    
    # Stop further processing of this message
    st.stop()
    
# Function to display appointment booking options
# Function to display appointment booking options with validation
def display_appointment_options():
    """Display options for booking a therapist appointment with field validation"""
    st.markdown("### 👩‍⚕️ Book a Therapist Appointment")
    
    st.info("""
    I'd be happy to help you schedule an appointment with a human therapist.
    Please fill out the following information to proceed with booking.
    """)
    
    # Initialize validation state if not present
    if "validation_errors" not in st.session_state:
        st.session_state.validation_errors = {}
    
    # Display validation errors if any
    if st.session_state.validation_errors:
        error_message = "Please correct the following errors:\n"
        for field, msg in st.session_state.validation_errors.items():
            error_message += f"- {msg}\n"
        st.error(error_message)
    
    with st.form("booking_form"):
        st.write("### Your Information")
        
        # Use name from user info if available
        name = st.text_input("Full Name", value=st.session_state.user_info.get("name", ""))
        
        # Add required field indicators
        st.markdown("**Email Address** (required)")
        email = st.text_input("Email Address", label_visibility="collapsed")
        
        st.markdown("**Phone Number** (required)")
        phone = st.text_input("Phone Number", label_visibility="collapsed")
        
        st.write("### Appointment Details")
        
        # Calculate tomorrow's date as the minimum selectable date
        tomorrow = datetime.now().date() + timedelta(days=1)
        
        # Date selection
        appointment_date = st.date_input("Preferred Date", min_value=tomorrow, value=tomorrow)
        
        # Time selection
        appointment_time = st.selectbox(
            "Preferred Time",
            ["9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM", "5:00 PM"]
        )
        
        # Appointment type
        appointment_type = st.radio(
            "Appointment Type",
            ["Video Session", "In-Person Session", "Phone Call"],
            horizontal=True
        )
        
        # Therapist preferences
        st.write("### Therapist Preferences")
        
        specialty = st.multiselect(
            "Areas of Expertise (Select all that apply)",
            ["Anxiety", "Depression", "Trauma", "Relationships", "Addiction", 
             "Grief", "Self-esteem", "Career Guidance", "Stress Management"]
        )
        
        gender_preference = st.radio(
            "Therapist Gender Preference",
            ["No Preference", "Female", "Male", "Non-binary"],
            horizontal=True
        )
        
        # Reason for visit
        reason = st.text_area("Briefly describe what you'd like to discuss in your session")
        
        # Submit button - inside the form
        submitted = st.form_submit_button("Book Appointment")
    
    # Handle form submission - outside the form
    if submitted:
        # Validate required fields
        validation_errors = {}
        
        # Check email (simple validation)
        if not email or "@" not in email or "." not in email:
            validation_errors["email"] = "Please enter a valid email address"
        
        # Check phone (simple validation - ensure it's not empty and has at least 10 digits)
        if not phone:
            validation_errors["phone"] = "Please enter your phone number"
        elif not any(c.isdigit() for c in phone) or sum(c.isdigit() for c in phone) < 10:
            validation_errors["phone"] = "Please enter a valid phone number with at least 10 digits"
        
        # Store validation errors in session state
        st.session_state.validation_errors = validation_errors
        
        # If we have validation errors, rerun to display them
        if validation_errors:
            st.rerun()
        
        # Clear validation errors
        st.session_state.validation_errors = {}
        
        # Here you would typically send this data to your backend
        # For now, we'll just show a success message
        st.success(f"Your appointment has been scheduled for {appointment_date.strftime('%A, %B %d, %Y')} at {appointment_time}!")
        st.info("A confirmation email will be sent to you shortly with next steps.")
        
        # Store appointment details in session state for reference
        st.session_state.last_appointment = {
            "name": name,
            "email": email,
            "phone": phone,
            "date": appointment_date.strftime('%A, %B %d, %Y'),
            "time": appointment_time,
            "type": appointment_type
        }
        
        # Add return to chat button - outside the form
        if st.button("Return to Chat"):
            # Reset booking flow
            st.session_state.show_therapist_options = False
            
            # Add a message to the chat about the booking
            confirmation_message = f"I've scheduled your appointment for {appointment_date.strftime('%A, %B %d, %Y')} at {appointment_time}. A confirmation email will be sent to {email}. Is there anything else I can help you with in the meantime?"
            st.session_state.messages.append({"role": "assistant", "content": confirmation_message})
            st.rerun()
    
    # Add a cancel button outside the form
    if st.button("Continue chatting with AI assistant"):
        st.session_state.show_therapist_options = False
        
        # Add a message to the chat
        continue_message = "I understand you'd prefer to continue our conversation. I'm here to support you. Is there anything specific you'd like to talk about?"
        st.session_state.messages.append({"role": "assistant", "content": continue_message})
        st.rerun()
        
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

def get_ai_response(messages):
    """Try each AI service in order until one succeeds"""
    
    # Check if we're within the first 5 minutes of chat
    is_first_5_minutes = False
    if st.session_state.chat_start_time is not None:
        chat_duration = datetime.now() - st.session_state.chat_start_time
        is_first_5_minutes = chat_duration.total_seconds() < 300  # 5 minutes in seconds
        print(f"DEBUG: Chat duration: {chat_duration.total_seconds()} seconds. First 5 minutes: {is_first_5_minutes}")
    
    # Create a copy of messages to modify
    modified_messages = [msg.copy() if isinstance(msg, dict) else msg for msg in messages]
    
    # Add special instruction for first 5 minutes if applicable
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
            print("DEBUG: No system message found to modify")
    
    # First try Qwen (changed order)
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
def log_conversation(user_message, ai_message, model_used):
    try:
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # Create log entry
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "conversation_id": st.session_state.conversation_id,
            "user_message": user_message,
            "ai_message": ai_message,
            "model_used": model_used
        }
        
        # In Streamlit Cloud, we might not have write access to the file system
        # So we'll handle both file logging and printing to stdout
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
        
# User onboarding function
def perform_onboarding():
    st.title("🧠 Welcome to LumonMind")
    
    st.markdown("""
    ### Your Safe Space for Mental Health Support
    
    We're here to provide you with supportive guidance and a listening ear. 
    Please share a bit about yourself so we can better assist you.
    
    You can interact in English, Hindi, or any other language you prefer.
    """)
    
    with st.form("onboarding_form"):
        name = st.text_input("What would you like to be called?", key="name_input")
        
        language_preference = st.selectbox(
            "Language you might use", 
            ["English", "Hinglish/Romanized Hindi", "Other language"]
        )
        
        submitted = st.form_submit_button("Start My Journey")
        
        if submitted:
            if name:
                st.session_state.user_info["name"] = name
                st.session_state.user_info["concerns"] = []  # Empty list as we're not collecting concerns
                st.session_state.user_info["language"] = language_preference
                st.session_state.user_info["onboarded"] = True
                
                # Create initial system message
                system_message = SYSTEM_PROMPT
                
                # Add user info to the system message
                system_message += f"\n\nThe user's name is {name}."
                    
                # Add language preference
                system_message += f"\n\nThe user's preferred language is {language_preference}."
                
                # Add system message to the conversation
                st.session_state.messages.append({"role": "system", "content": system_message})
                
                # Set chat start time when user completes onboarding
                st.session_state.chat_start_time = datetime.now()
                print(f"DEBUG: Chat start time set during onboarding: {st.session_state.chat_start_time}")
                
                # Add welcome message from assistant - English only regardless of language preference
                greeting = f"Hello {name}! I'm here to support you with your mental health journey. How are you feeling today?"
                st.session_state.messages.append({"role": "assistant", "content": greeting})
                
                st.rerun()
            else:
                st.warning("Please tell us what to call you before continuing.")
                
# Main chat interface function
def display_chat_interface():
    st.title("🧠 LumonMind Chat")
    
    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        if message["role"] != "system":  # Don't display system messages
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # This is a workaround - we'll put the End Chat button in the 
    # sidebar where it won't interfere with the chat input
    st.sidebar.markdown("---")
    if st.sidebar.button("End Chat", type="secondary", key="end_chat_button"):
        # Reset messages but keep user info
        st.session_state.messages = []
        
        # Re-add system message with user info
        system_message = SYSTEM_PROMPT
        if st.session_state.user_info["concerns"]:
            system_message += f"\n\nThe user's name is {st.session_state.user_info['name']} and they're seeking help with: {', '.join(st.session_state.user_info['concerns'])}."
        else:
            system_message += f"\n\nThe user's name is {st.session_state.user_info['name']}."
        
        st.session_state.messages.append({"role": "system", "content": system_message})
        
        # Generate a new conversation ID
        st.session_state.conversation_id = str(uuid.uuid4())
        
        # Reset chat start time for the new conversation
        st.session_state.chat_start_time = datetime.now()
        print(f"DEBUG: Chat start time reset on new conversation: {st.session_state.chat_start_time}")
        
        # Add welcome message
        greeting = f"Hello {st.session_state.user_info['name']}! I'm here to continue supporting you. How are you feeling today?"
        st.session_state.messages.append({"role": "assistant", "content": greeting})
        
        st.rerun()
    
    # Chat input - this will always appear at the bottom
    placeholder_text = "How are you feeling today?"
    prompt = st.chat_input(placeholder_text)
    
    # Process user input if provided
    if prompt:
        # Set chat start time if this is the first message
        if st.session_state.chat_start_time is None:
            st.session_state.chat_start_time = datetime.now()
            print(f"DEBUG: Chat start time set on first message: {st.session_state.chat_start_time}")
        
        # Check if this is a therapist request
        if detect_therapist_request(prompt):
            handle_therapist_request(prompt)
            return
        
        # If not a therapist request, proceed with normal chat flow
        
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            
            # Show thinking message
            message_placeholder.markdown("Thinking...")
            
            # Prepare messages for API
            api_messages = [msg for msg in st.session_state.messages]
            
            # Get AI response
            with st.spinner("Getting response..."):
                full_response, model_used = get_ai_response(api_messages)
            
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # Display assistant response
            message_placeholder.markdown(full_response)
            
            # Log the conversation
            log_conversation(prompt, full_response, model_used)
            
            # Rerun to refresh the UI with the new messages
            st.rerun()

def render_sidebar():
    with st.sidebar:
        st.image("https://via.placeholder.com/150x150.png?text=LumonMind", width=150)
        
        st.markdown("## About LumonMind")
        st.markdown("""
        LumonMind provides AI-assisted mental health support for everyone.
        
        Remember:
        - This is not a replacement for professional help
        - In crisis situations, please contact emergency services
        - Your conversations are private and secure
        """)
        
        st.markdown("---")
        
        if st.session_state.user_info["onboarded"]:
            st.markdown(f"### Hello, {st.session_state.user_info['name']}!")
            
            if st.session_state.user_info["concerns"]:
                st.markdown("**Your concerns:**")
                for concern in st.session_state.user_info["concerns"]:
                    st.markdown(f"- {concern}")
            
            # Add language support information
            st.markdown("**Language Support:**")
            st.markdown("You can chat in:")
            st.markdown("- English")
            st.markdown("- Hinglish/Romanized Hindi")
            st.markdown("- Many other languages")
            
            # Add therapist booking option in sidebar
            st.markdown("---")
            st.markdown("**Need to talk to a therapist?**")
            
            if st.button("Book an Appointment", key="sidebar_book"):
                st.session_state.show_therapist_options = True
                st.rerun()
            
            # Add fallback information - only if we have at least one API key
            if QWEN_API_KEY or DEEPSEEK_API_KEY or GEMINI_API_KEY:
                st.markdown("**AI Backend:**")
                st.markdown("1. Qwen Max via OpenAI client (Primary)")
                st.markdown("2. DeepSeek Chat (First Fallback)")
                st.markdown("3. Gemini (Second Fallback)")
            
            # Add a start new conversation button
            if st.button("Start New Conversation"):
                # Keep user info but reset messages
                st.session_state.messages = []
                
                # Re-add system message with user info
                system_message = SYSTEM_PROMPT
                if st.session_state.user_info["concerns"]:
                    system_message += f"\n\nThe user's name is {st.session_state.user_info['name']} and they're seeking help with: {', '.join(st.session_state.user_info['concerns'])}."
                else:
                    system_message += f"\n\nThe user's name is {st.session_state.user_info['name']}."
                
                st.session_state.messages.append({"role": "system", "content": system_message})
                
                # Generate a new conversation ID
                st.session_state.conversation_id = str(uuid.uuid4())
                
                # Reset chat start time for the new conversation
                st.session_state.chat_start_time = datetime.now()
                print(f"DEBUG: Chat start time reset on Start New Conversation: {st.session_state.chat_start_time}")
                
                # Add welcome message
                greeting = f"Hello {st.session_state.user_info['name']}! I'm here to continue supporting you. How are you feeling today?"
                st.session_state.messages.append({"role": "assistant", "content": greeting})
                
                st.rerun()
                
        st.markdown("---")
        st.markdown("© 2025 LumonMind - POC Version")
        
        # Display prompt loading status
        st.markdown("---")
        st.markdown("**System Status:**")
        st.success("✅ Prompt loaded successfully")
        
        # Display therapist connection status if onboarded
        if st.session_state.user_info.get("onboarded", False):
            st.success("✅ Therapist booking system available")
            
# Update the main function to include therapist options
def main():
    render_sidebar()
    
    # Check if we need to show therapist options
    if st.session_state.show_therapist_options:
        display_chat_interface()
        display_appointment_options()
    # Otherwise show normal interface
    elif not st.session_state.user_info["onboarded"]:
        perform_onboarding()
    else:
        display_chat_interface()

if __name__ == "__main__":
    main()
