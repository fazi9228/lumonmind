# LumonMind: Mental Health Support App

LumonMind is an AI-powered mental health support application built with Streamlit. It provides a conversational interface for users to discuss their mental health concerns and offers the option to book appointments with human therapists when needed.

## Features

- Conversational AI support for mental health discussions
- Multi-language support including English and Romanized Hindi
- User onboarding to collect initial concerns
- Therapist appointment booking system
- Multiple LLM backends with automatic fallback (Qwen, DeepSeek, Gemini)

## Setup and Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/lumonmind.git
   cd lumonmind
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file with your API keys:
   ```
   QWEN_API_KEY=your_qwen_api_key
   DEEPSEEK_API_KEY=your_deepseek_api_key
   GEMINI_API_KEY=your_gemini_api_key
   ```

5. Create a `lumonmind_prompt.md` file with your system prompt.

## Running the Application

Start the application with:
```
streamlit run app.py
```

## Project Structure

- `app.py`: Main application file
- `lumonmind_prompt.md`: System prompt for the AI assistant
- `.env`: Environment variables (API keys)
- `requirements.txt`: Python dependencies
- `README.md`: Project documentation

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

[MIT](LICENSE)
