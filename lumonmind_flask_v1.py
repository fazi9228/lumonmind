import requests
import json

class LumonMindClient:
    """Python client for the LumonMind API"""
    
    def __init__(self, base_url="http://localhost:5000"):
        """
        Initialize the LumonMind API client
        
        Args:
            base_url (str): Base URL of the LumonMind API
        """
        self.base_url = base_url
        self.session_id = None
    
    def health_check(self):
        """Check if the API is up and running"""
        response = requests.get(f"{self.base_url}/api/health")
        return response.json()
    
    def create_session(self):
        """Create a new session"""
        response = requests.post(f"{self.base_url}/api/session/new")
        data = response.json()
        
        if data.get('status') == 'success':
            self.session_id = data.get('session_id')
        
        return data
    
    def onboard_user(self, name, concerns=None, language="English"):
        """
        Onboard a user with their information
        
        Args:
            name (str): User's name
            concerns (list): List of user's concerns
            language (str): Preferred language
            
        Returns:
            dict: API response
        """
        if not self.session_id:
            raise ValueError("No active session. Call create_session() first.")
        
        if concerns is None:
            concerns = []
        
        payload = {
            "name": name,
            "concerns": concerns,
            "language": language
        }
        
        response = requests.post(
            f"{self.base_url}/api/session/{self.session_id}/onboard",
            json=payload
        )
        
        return response.json()
    
    def send_message(self, message):
        """
        Send a chat message
        
        Args:
            message (str): User's message
            
        Returns:
            dict: AI response
        """
        if not self.session_id:
            raise ValueError("No active session. Call create_session() first.")
        
        payload = {"message": message}
        
        response = requests.post(
            f"{self.base_url}/api/session/{self.session_id}/chat",
            json=payload
        )
        
        return response.json()
    
    def book_therapist(self, name, email, phone, appointment_date, appointment_time, 
                      appointment_type, specialty=None, gender_preference="No Preference", reason=""):
        """
        Book a therapist appointment
        
        Args:
            name (str): Full name
            email (str): Email address
            phone (str): Phone number
            appointment_date (str): Date in YYYY-MM-DD format
            appointment_time (str): Time (e.g., "10:00 AM")
            appointment_type (str): One of "Video Session", "In-Person Session", "Phone Call"
            specialty (list): List of specialties
            gender_preference (str): Gender preference
            reason (str): Reason for appointment
            
        Returns:
            dict: API response
        """
        if not self.session_id:
            raise ValueError("No active session. Call create_session() first.")
        
        if specialty is None:
            specialty = []
        
        payload = {
            "name": name,
            "email": email,
            "phone": phone,
            "appointment_date": appointment_date,
            "appointment_time": appointment_time,
            "appointment_type": appointment_type,
            "specialty": specialty,
            "gender_preference": gender_preference,
            "reason": reason
        }
        
        response = requests.post(
            f"{self.base_url}/api/session/{self.session_id}/therapist",
            json=payload
        )
        
        return response.json()
    
    def get_chat_history(self):
        """Get the chat history for the current session"""
        if not self.session_id:
            raise ValueError("No active session. Call create_session() first.")
        
        response = requests.get(f"{self.base_url}/api/session/{self.session_id}/history")
        return response.json()
    
    def end_conversation(self):
        """End the current conversation but keep the session"""
        if not self.session_id:
            raise ValueError("No active session. Call create_session() first.")
        
        response = requests.post(f"{self.base_url}/api/session/{self.session_id}/end")
        return response.json()
    
    def delete_session(self):
        """Delete the current session completely"""
        if not self.session_id:
            raise ValueError("No active session. Call create_session() first.")
        
        response = requests.delete(f"{self.base_url}/api/session/{self.session_id}")
        data = response.json()
        
        if data.get('status') == 'success':
            self.session_id = None
        
        return data


# Example usage
if __name__ == "__main__":
    client = LumonMindClient()
    
    # Check if API is running
    health = client.health_check()
    print(f"API Status: {health}")
    
    # Create a new session
    session = client.create_session()
    print(f"Session created: {session}")
    
    # Onboard user
    onboarding = client.onboard_user(
        name="John Doe",
        concerns=["Anxiety", "Stress & Burnout"],
        language="English"
    )
    print(f"User onboarded: {onboarding}")
    
    # Send a message
    response = client.send_message("I've been feeling really stressed at work lately.")
    print(f"AI response: {response}")
    
    # Get chat history
    history = client.get_chat_history()
    print(f"Chat history: {json.dumps(history, indent=2)}")
    
    # End conversation
    end_result = client.end_conversation()
    print(f"Conversation ended: {end_result}")
    
    # Delete session
    delete_result = client.delete_session()
    print(f"Session deleted: {delete_result}")