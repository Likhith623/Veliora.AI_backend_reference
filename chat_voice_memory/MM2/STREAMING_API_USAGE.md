# Streaming Audio API Usage Guide

This document explains how to properly use the streaming audio endpoints in our API.

## Understanding Streaming Responses

Our streaming audio endpoints (`/stream-audio` and `/stream-audio-raw`) provide real-time audio generation with different formats:

1. **`/stream-audio`**: Returns a stream of newline-delimited JSON objects (NDJSON) containing base64-encoded audio chunks
2. **`/stream-audio-raw`**: Returns raw audio bytes directly

## Why Swagger UI Shows "Can't parse JSON"

When testing the `/stream-audio` endpoint in Swagger UI, you may see "Can't parse JSON. Raw result:" followed by the streamed data. This is **expected behavior** and not an error with the API.

Swagger UI tries to parse the entire response as a single JSON object, but the endpoint returns a stream of multiple JSON objects separated by newlines (NDJSON format). While each individual JSON object is valid, the concatenation of multiple JSON objects is not valid as a single JSON document.

## Proper Client Usage

### Using cURL

To correctly consume the streaming API with cURL:

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/stream-audio' \
  -H 'Accept: application/x-ndjson' \
  -H 'Content-Type: application/json' \
  -d '{
  "transcript": "Hi",
  "bot_id": "delhi_mentor_male",
  "output_format": {
    "container": "wav",
    "encoding": "pcm_f32le", 
    "sample_rate": 22050
  }
}' \
  --output stream_response.ndjson
```

Then process the NDJSON file by reading it line by line, where each line is a valid JSON object.

### JavaScript/Frontend Implementation

```javascript
async function streamAudio(transcript, botId) {
  const response = await fetch('http://127.0.0.1:8000/stream-audio', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/x-ndjson'
    },
    body: JSON.stringify({
      transcript: transcript,
      bot_id: botId,
      output_format: {
        container: "wav",
        encoding: "pcm_f32le",
        sample_rate: 22050
      }
    })
  });

  // Get a reader from the response body stream
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  // Function to process audio chunks as they arrive
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    // Decode the received bytes to text
    buffer += decoder.decode(value, { stream: true });
    
    // Process complete JSON objects
    let newlineIndex;
    while ((newlineIndex = buffer.indexOf('\n')) >= 0) {
      // Extract a complete JSON object
      const line = buffer.slice(0, newlineIndex);
      buffer = buffer.slice(newlineIndex + 1);
      
      if (line.trim()) {
        // Parse the JSON object
        const chunk = JSON.parse(line);
        
        // Process based on chunk type
        switch (chunk.type) {
          case 'audio_chunk':
            // Convert base64 to audio and play or buffer
            const audioData = atob(chunk.data);
            // Process audio data (e.g., add to audio buffer)
            playAudioChunk(audioData);
            break;
            
          case 'stream_complete':
            console.log('Stream completed');
            // Handle completion (e.g., finalize audio playback)
            break;
            
          case 'error':
            console.error('Stream error:', chunk.message);
            break;
        }
      }
    }
  }
}

function playAudioChunk(audioData) {
  // Implementation to play the audio chunk
  // This will depend on your audio playback library/approach
}
```

### Python Client

```python
import json
import base64
import requests

def stream_audio(transcript, bot_id):
    url = "http://127.0.0.1:8000/stream-audio"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/x-ndjson"
    }
    data = {
        "transcript": transcript,
        "bot_id": bot_id,
        "output_format": {
            "container": "wav",
            "encoding": "pcm_f32le",
            "sample_rate": 22050
        }
    }
    
    # Use stream=True to get the response as it's generated
    with requests.post(url, headers=headers, json=data, stream=True) as response:
        # Process each line (each JSON object) as it arrives
        for line in response.iter_lines():
            if line:
                # Parse the JSON object
                chunk = json.loads(line)
                
                # Process based on chunk type
                if chunk["type"] == "audio_chunk":
                    # Decode the base64 audio data
                    audio_data = base64.b64decode(chunk["data"])
                    # Process the audio data
                    process_audio_chunk(audio_data)
                elif chunk["type"] == "stream_complete":
                    print("Stream completed")
                elif chunk["type"] == "error":
                    print(f"Error: {chunk['message']}")

def process_audio_chunk(audio_data):
    # Implementation to process the audio chunk
    # For example, write to a file or play it
    pass
```

## Conclusion

The "Can't parse JSON" message in Swagger UI is normal for streaming responses and doesn't indicate a problem with the API. To properly use these endpoints, clients should process the response as a stream of individual JSON objects rather than a single JSON document.
