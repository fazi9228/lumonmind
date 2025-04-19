# LumonMind API Integration Guide

## Overview

This document explains how to integrate the LumonMind application with multiple AI provider APIs (Qwen, DeepSeek, and Gemini) to power the mental health chatbot functionality.

## Prerequisites

- Node.js (v14+)
- npm or yarn
- Valid API keys for at least one of the following:
  - Qwen via Aliyun Dashscope
  - DeepSeek
  - Google Gemini

## Required Dependencies

Install the following packages:

```bash
npm install openai axios @google/generative-ai dotenv
```

## Environment Setup

1. Create a `.env` file in your project root with your API keys:

```
# LumonMind API Keys
QWEN_API_KEY=your_qwen_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

2. Load environment variables in your application:

```javascript
require('dotenv').config();
```

## API Integration Functions

### Qwen API Integration

```javascript
const { OpenAI } = require('openai');

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
      model: 'qwen-max',
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
```

### DeepSeek API Integration

```javascript
const axios = require('axios');

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
```

### Gemini API Integration

```javascript
const { GoogleGenerativeAI } = require('@google/generative-ai');

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
```

## Fallback Mechanism Implementation

For reliability, implement a fallback mechanism that tries each API in sequence:

```javascript
async function getAIResponse(messages) {
  // First try Qwen
  let response = await callQwenAPI(messages);
  if (response) {
    console.log('Using Qwen response');
    return { content: response, provider: 'qwen' };
  }
  
  // Then try DeepSeek
  response = await callDeepSeekAPI(messages);
  if (response) {
    console.log('Using DeepSeek response');
    return { content: response, provider: 'deepseek' };
  }
  
  // Finally try Gemini
  response = await callGeminiAPI(messages);
  if (response) {
    console.log('Using Gemini response');
    return { content: response, provider: 'gemini' };
  }
  
  // If all fail, return an error message
  return { 
    content: "I'm sorry, I'm having connectivity issues right now. Please try again later.", 
    provider: 'error' 
  };
}
```

## Message Format

All APIs expect messages in the following format:

```javascript
const messages = [
  { role: 'system', content: 'You are a helpful mental health assistant.' },
  { role: 'user', content: 'I\'m feeling anxious today.' },
  { role: 'assistant', content: 'I understand that anxiety can be difficult...' },
  { role: 'user', content: 'What are some coping techniques?' }
];
```

## Integration with Angular

1. Create a service for API communication:

```typescript
// ai-service.ts
import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, from } from 'rxjs';
import { environment } from '../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class AiService {
  constructor(private http: HttpClient) {}
  
  async getAIResponse(messages: any[]): Promise<any> {
    // Import and use the getAIResponse function
    // You'll need to adapt the Node.js code for the browser environment
  }
}
```

2. Call the service from your component:

```typescript
// chat.component.ts
import { Component } from '@angular/core';
import { AiService } from '../services/ai.service';

@Component({
  selector: 'app-chat',
  templateUrl: './chat.component.html'
})
export class ChatComponent {
  messages: any[] = [];
  newMessage: string = '';
  
  constructor(private aiService: AiService) {}
  
  async sendMessage() {
    // Add user message
    this.messages.push({ role: 'user', content: this.newMessage });
    
    // Format messages for API
    const apiMessages = [
      { role: 'system', content: 'You are a helpful mental health assistant.' },
      ...this.messages
    ];
    
    // Get AI response
    const response = await this.aiService.getAIResponse(apiMessages);
    
    // Add assistant response
    this.messages.push({ role: 'assistant', content: response.content });
    
    // Clear input
    this.newMessage = '';
  }
}
```

## Troubleshooting

### Common Issues:

1. **API Key Errors**
   - Verify your API keys are correct and have sufficient permissions
   - Check for whitespace or special characters in your .env file

2. **Network Errors**
   - Ensure your application has internet access
   - Check if your network requires a proxy for external API calls

3. **Format Errors**
   - Confirm your messages array has the correct structure
   - Verify that roles are lowercase ('user', 'assistant', 'system')

4. **Service Limits**
   - API providers may have rate limits or token quotas
   - Check your API usage dashboard if you're getting quota errors

## Security Notes

- Never expose API keys in client-side code
- For production, use a backend proxy to make API calls
- Implement proper error handling to avoid exposing sensitive information
