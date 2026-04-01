# FastAPI Server

## Requirements (requirements.txt)

```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
pydantic==2.5.0
requests==2.31.0
python-dotenv==1.0.0
gradio-client==0.7.1
litellm==1.17.9
Pillow==10.1.0
sqlite3
```

## Environment Setup

Create a `.env` file in your project root:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

## Installation & Running

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

### 1. Health Check
```http
GET /
```

**Response:**
```json
{
  "message": "AI Chatbot API is running",
  "status": "healthy"
}
```

### 2. Get Available Bots
```http
GET /bots
```

**Response:**
```json
{
  "bots": ["jayden_lim"],
  "details": {
    "jayden_lim": {
      "name": "Jayden Lim",
      "origin": "singapore"
    }
  }
}
```

### 3. Chat with Bot (Main Endpoint)
```http
POST /chat
```

**Request Body:**
```json
{
  "bot_id": "jayden_lim",
  "email": "user@example.com",
  "message": "Hey, how are you doing?",
  "previous_conversation": "",
  "username": "user",
  "generate_selfie": true
}
```

**Response:**
```json
{
  "bot_response": "Yo bro! I'm doing great lah, just chilling at home. How about you?",
  "emotion_context": {
    "emotion": "happy",
    "location": "home",
    "action": "relaxing"
  },
  "selfie_image": "base64_encoded_image_string",
  "selfie_url": null,
  "conversation_history": "user: Hey, how are you doing?\nJayden Lim: Yo bro! I'm doing great lah...",
  "status": "success"
}
```

### 4. Generate Selfie Only
```http
POST /generate-selfie?bot_id=jayden_lim&message=I'm feeling sad today&email=user@example.com
```

**Response:**
```json
{
  "selfie_image": "base64_encoded_image_string",
  "emotion_context": {
    "emotion": "sad",
    "location": "room",
    "action": "sitting"
  },
  "status": "success"
}
```

### 5. Detect Emotion Only
```http
POST /detect-emotion?message=I'm really excited about this project!
```

**Response:**
```json
{
  "emotion_context": {
    "emotion": "excited",
    "location": "unknown",
    "action": "talking"
  },
  "status": "success"
}
```

## Frontend Integration Examples

### JavaScript/Node.js
```javascript
// Chat with bot
const chatResponse = await fetch('http://localhost:8000/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    bot_id: 'jayden_lim',
    email: 'user@example.com',
    message: 'Hello there!',
    previous_conversation: '',
    username: 'user',
    generate_selfie: true
  })
});

const data = await chatResponse.json();
console.log('Bot response:', data.bot_response);

// Display selfie image if available
if (data.selfie_image) {
  const img = document.createElement('img');
  img.src = `data:image/png;base64,${data.selfie_image}`;
  document.body.appendChild(img);
}
```

### React Example
```jsx
import React, { useState } from 'react';

function ChatBot() {
  const [message, setMessage] = useState('');
  const [conversation, setConversation] = useState('');
  const [botResponse, setBotResponse] = useState('');
  const [selfieImage, setSelfieImage] = useState('');

  const sendMessage = async () => {
    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          bot_id: 'jayden_lim',
          email: 'user@example.com',
          message: message,
          previous_conversation: conversation,
          username: 'user',
          generate_selfie: true
        })
      });

      const data = await response.json();
      setBotResponse(data.bot_response);
      setConversation(data.conversation_history);
      
      if (data.selfie_image) {
        setSelfieImage(`data:image/png;base64,${data.selfie_image}`);
      }
    } catch (error) {
      console.error('Error:', error);
    }
  };

  return (
    <div>
      <input 
        type="text" 
        value={message} 
        onChange={(e) => setMessage(e.target.value)} 
        placeholder="Type your message..."
      />
      <button onClick={sendMessage}>Send</button>
      
      {botResponse && <div>Bot: {botResponse}</div>}
      {selfieImage && <img src={selfieImage} alt="Bot selfie" />}
    </div>
  );
}

export default ChatBot;
```

### Python Client Example
```python
import requests
import base64
from PIL import Image
import io

def chat_with_bot(message, previous_conversation=""):
    url = "http://localhost:8000/chat"
    payload = {
        "bot_id": "jayden_lim",
        "email": "user@example.com",
        "message": message,
        "previous_conversation": previous_conversation,
        "username": "user",
        "generate_selfie": True
    }
    
    response = requests.post(url, json=payload)
    data = response.json()
    
    print(f"Bot: {data['bot_response']}")
    
    # Save selfie if available
    if data.get('selfie_image'):
        image_data = base64.b64decode(data['selfie_image'])
        image = Image.open(io.BytesIO(image_data))
        image.save('bot_selfie.png')
        print("Selfie saved as bot_selfie.png")
    
    return data['conversation_history']

# Usage
conversation = chat_with_bot("Hey, how's it going?")
conversation = chat_with_bot("Tell me about Singapore!", conversation)
```

## Error Handling

All endpoints return consistent error responses:

```json
{
  "error": "Error description",
  "status": "error"
}
```

Common HTTP status codes:
- `200`: Success
- `400`: Bad Request (invalid bot_id, missing parameters)
- `500`: Internal Server Error (API failures, processing errors)

## Production Deployment

### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables for Production
```env
GEMINI_API_KEY=your_production_key
CORS_ORIGINS=https://yourdomain.com,https://api.yourdomain.com
LOG_LEVEL=INFO
```

### Security Considerations

1. **CORS Configuration**: Update `allow_origins` in production
2. **API Key Security**: Use secure secret management
3. **Rate Limiting**: Implement rate limiting for production
4. **Input Validation**: All inputs are validated via Pydantic models
5. **Error Logging**: Comprehensive logging for debugging

### Performance Optimization

1. **Caching**: Consider caching emotion detection results
2. **Async Operations**: All I/O operations are async
3. **Connection Pooling**: Gradio client is initialized once and reused
4. **Image Compression**: Consider compressing base64 images for faster response times

## Key Features Preserved

✅ **All original Streamlit logic preserved**
✅ **Emotion detection from conversation**
✅ **Dynamic selfie generation based on emotion**
✅ **Conversation history management**
✅ **Multiple persona support**
✅ **Error handling and fallbacks**
✅ **Image processing and base64 encoding**
✅ **Gemini API integration**
✅ **FaceID selfie generation**

## Scalability Features

- **Async/await support** for concurrent requests
- **Pydantic models** for request/response validation
- **Modular service architecture** for easy maintenance
- **Comprehensive logging** for monitoring
- **Health check endpoints** for load balancers
- **CORS support** for web frontend integration
