// -------------------------------------------------------------------------
// QWEN API Integration Example
// -------------------------------------------------------------------------
// Using the OpenAI compatible endpoint for Qwen via Dashscope

// Install dependencies:
// npm install openai dotenv

const { OpenAI } = require('openai');
require('dotenv').config();

// Call Qwen API function
async function callQwenAPI(messages) {
  try {
    // Get API key from .env
    const QWEN_API_KEY = process.env.QWEN_API_KEY;
    
    if (!QWEN_API_KEY) {
      console.error('Qwen API key is missing');
      return null;
    }
    
    // Create OpenAI client with Aliyun's Dashscope endpoint
    const client = new OpenAI({
      apiKey: QWEN_API_KEY,
      baseURL: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1'
    });
    
    // Call the API
    const completion = await client.chat.completions.create({
      model: 'qwen-max', // or whatever model version you're using
      messages: messages,
      temperature: 0.7,
      max_tokens: 2000
    });
    
    // Extract and return the content
    return completion.choices[0].message.content;
  } catch (error) {
    console.error('Qwen API Error:', error.message);
    return null;
  }
}

// Example usage:
async function testQwenAPI() {
  const messages = [
    { role: 'system', content: 'You are a helpful mental health assistant.' },
    { role: 'user', content: 'I\'m feeling anxious today.' }
  ];
  
  const response = await callQwenAPI(messages);
  console.log('Qwen Response:', response);
}

// testQwenAPI();

// -------------------------------------------------------------------------
// DEEPSEEK API Integration Example
// -------------------------------------------------------------------------

// Install dependencies:
// npm install axios dotenv

const axios = require('axios');
// require('dotenv').config(); // Already loaded above

// Call DeepSeek API function
async function callDeepSeekAPI(messages) {
  try {
    // Get API key from .env
    const DEEPSEEK_API_KEY = process.env.DEEPSEEK_API_KEY;
    
    if (!DEEPSEEK_API_KEY) {
      console.error('DeepSeek API key is missing');
      return null;
    }
    
    const headers = {
      'Authorization': `Bearer ${DEEPSEEK_API_KEY}`,
      'Content-Type': 'application/json'
    };
    
    const payload = {
      model: 'deepseek-chat',
      messages: messages,
      temperature: 0.7,
      max_tokens: 2000
    };
    
    const response = await axios.post(
      'https://api.deepseek.com/v1/chat/completions',
      payload,
      { headers }
    );
    
    return response.data.choices[0].message.content;
  } catch (error) {
    console.error('DeepSeek API Error:', error.response?.data || error.message);
    return null;
  }
}

// Example usage:
async function testDeepSeekAPI() {
  const messages = [
    { role: 'system', content: 'You are a helpful mental health assistant.' },
    { role: 'user', content: 'I\'m feeling anxious today.' }
  ];
  
  const response = await callDeepSeekAPI(messages);
  console.log('DeepSeek Response:', response);
}

// testDeepSeekAPI();

// -------------------------------------------------------------------------
// GEMINI API Integration Example
// -------------------------------------------------------------------------

// Install dependencies:
// npm install @google/generative-ai dotenv

const { GoogleGenerativeAI } = require('@google/generative-ai');
// require('dotenv').config(); // Already loaded above

// Call Gemini API function
async function callGeminiAPI(messages) {
  try {
    // Get API key from .env
    const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
    
    if (!GEMINI_API_KEY) {
      console.error('Gemini API key is missing');
      return null;
    }
    
    // Initialize the Google Generative AI
    const genAI = new GoogleGenerativeAI(GEMINI_API_KEY);
    const model = genAI.getGenerativeModel({ model: 'gemini-1.5-pro-latest' });
    
    // Convert our message format to Gemini format
    const geminiMessages = [];
    let systemPrompt = '';
    
    // Extract system prompt if present
    for (const msg of messages) {
      if (msg.role === 'system') {
        systemPrompt = msg.content;
        break;
      }
    }
    
    // Build conversation parts
    for (const msg of messages) {
      if (msg.role === 'system') continue; // Skip system message
      
      if (msg.role === 'user') {
        // For first user message, prepend system prompt if available
        if (geminiMessages.length === 0 && systemPrompt) {
          geminiMessages.push({
            role: 'user',
            parts: [{ text: systemPrompt + '\n\nUser: ' + msg.content }]
          });
        } else {
          geminiMessages.push({
            role: 'user',
            parts: [{ text: msg.content }]
          });
        }
      } else if (msg.role === 'assistant') {
        geminiMessages.push({
          role: 'model',
          parts: [{ text: msg.content }]
        });
      }
    }
    
    // Handle empty conversation case
    if (geminiMessages.length === 0 && systemPrompt) {
      geminiMessages.push({
        role: 'user',
        parts: [{ text: systemPrompt }]
      });
    }
    
    // Call the API
    const result = await model.generateContent({
      contents: geminiMessages,
      generationConfig: {
        temperature: 0.7,
        maxOutputTokens: 2000,
      }
    });
    
    return result.response.text();
  } catch (error) {
    console.error('Gemini API Error:', error.message);
    return null;
  }
}

// Example usage:
async function testGeminiAPI() {
  const messages = [
    { role: 'system', content: 'You are a helpful mental health assistant.' },
    { role: 'user', content: 'I\'m feeling anxious today.' }
  ];
  
  const response = await callGeminiAPI(messages);
  console.log('Gemini Response:', response);
}

// testGeminiAPI();

// -------------------------------------------------------------------------
// ENVIRONMENT FILE (.env) EXAMPLE
// -------------------------------------------------------------------------
/*
# LumonMind API Keys - save this as .env file
QWEN_API_KEY=your_qwen_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
*/

// -------------------------------------------------------------------------
// COMBINED USAGE WITH FALLBACK
// -------------------------------------------------------------------------

async function getAIResponse(messages) {
  // First try Qwen
  let response = await callQwenAPI(messages);
  if (response) {
    console.log('Using Qwen response');
    return response;
  }
  
  // Then try DeepSeek
  response = await callDeepSeekAPI(messages);
  if (response) {
    console.log('Using DeepSeek response');
    return response;
  }
  
  // Finally try Gemini
  response = await callGeminiAPI(messages);
  if (response) {
    console.log('Using Gemini response');
    return response;
  }
  
  // If all fail, return an error message
  return "I'm sorry, I'm having connectivity issues right now. Please try again later.";
}

// Example usage with fallback mechanism:
async function testWithFallback() {
  const messages = [
    { role: 'system', content: 'You are a helpful mental health assistant.' },
    { role: 'user', content: 'I\'m feeling anxious today.' }
  ];
  
  const response = await getAIResponse(messages);
  console.log('Final Response:', response);
}

// Run test with fallback
// testWithFallback();
