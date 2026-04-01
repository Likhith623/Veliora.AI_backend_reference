# TTS Optimization Quick Start Guide

## 🚀 Quick Setup

### 1. Environment Setup
Ensure your environment has the required API key:
```bash
export CARTESIA_API_KEY="your_cartesia_api_key_here"
```

### 2. Start the Server
```bash
cd /Users/likhith./Desktop/backend/NoviBE/MM2
uvicorn main:app --reload --port 8000
```

## 🎯 Testing TTS Optimizations

### Test Optimized TTS Endpoint
```bash
curl -X POST "http://localhost:8000/generate-audio-optimized" \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Hello! This is a test of the optimized TTS system.",
    "bot_id": "delhi_mentor_male"
  }'
```

### Test Cache Performance
```bash
# First call - will be cached
curl -X POST "http://localhost:8000/generate-audio-optimized" \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "This will be cached for faster subsequent calls.",
    "bot_id": "delhi_mentor_male"
  }'

# Second call - should hit cache (< 0.1s)
curl -X POST "http://localhost:8000/generate-audio-optimized" \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "This will be cached for faster subsequent calls.",
    "bot_id": "delhi_mentor_male"
  }'
```

### Check Performance Stats
```bash
# TTS Cache Statistics
curl "http://localhost:8000/tts-cache/stats"

# Comprehensive Performance Summary
curl "http://localhost:8000/tts-performance/summary"
```

## 📊 Expected Response Times

### Performance Targets:
- **Cache Hits**: < 0.1s
- **Short Text** (≤10 words): 1.0-1.5s
- **Medium Text** (11-20 words): 1.5-2.0s  
- **Long Text** (>20 words): 1.5-2.5s with parallel processing

### Response Format:
```json
{
  "voice_id": "fd2ada67-c2d9-4afe-b474-6386b87d8fc3",
  "audio_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA...",
  "cached": false,
  "generation_time": 1.847,
  "optimization_used": "word_by_word",
  "word_count": 23,
  "performance_target_met": true,
  "audio_format_used": {
    "container": "wav",
    "encoding": "pcm_s16le",
    "sample_rate": 16000
  }
}
```

## 🔧 Voice Call Integration

The voice call endpoint automatically uses optimized TTS:
```bash
curl -X POST "http://localhost:8000/voice-call" \
  -F "audio_file=@test_audio.wav" \
  -F "bot_id=delhi_mentor_male" \
  -F "email=test@example.com"
```

## 🎵 Audio Format Selection Logic

The system automatically chooses optimal formats:

- **Ultra Fast** (16kHz, 16-bit): Long text >20 words
- **Balanced** (22kHz, 32-bit): Medium text 10-20 words  
- **Balanced** (22kHz, 32-bit): Short text ≤10 words

## 💾 Cache Management

### View Cache Statistics:
```bash
curl "http://localhost:8000/tts-cache/stats"
```

### Clear Cache (Admin):
```bash
curl -X DELETE "http://localhost:8000/tts-cache/clear"
```

## 🔍 Performance Monitoring

### Real-time Performance Dashboard:
```bash
curl "http://localhost:8000/tts-performance/summary"
```

Response includes:
- Performance targets vs actual
- Cache hit rates
- Optimization recommendations
- Audio format configurations

## ⚡ Performance Test Script

Run comprehensive performance tests:
```bash
cd /Users/likhith./Desktop/backend/NoviBE/MM2
python test_tts_performance.py
```

## 🎯 Optimization Features Active

✅ **TTS Response Caching** - Near-instant repeated phrases  
✅ **Smart Audio Format Selection** - Optimal encoding per text type  
✅ **Word-by-Word Parallel Processing** - Faster long text generation  
✅ **Voice Call Integration** - All voice calls use optimizations  
✅ **Performance Monitoring** - Real-time metrics and recommendations  
✅ **Automatic Fallbacks** - Graceful degradation on errors  

## 🚨 Troubleshooting

### Performance Issues:
1. Check cache hit rate: `curl "http://localhost:8000/tts-cache/stats"`
2. Monitor generation times in server logs
3. Verify Cartesia API connectivity

### Cache Issues:
1. Verify `TTS_CACHE_ENABLED = True` in main.py
2. Check cache utilization in performance summary
3. Clear cache if needed: `curl -X DELETE "http://localhost:8000/tts-cache/clear"`

### Fallback Behavior:
- If optimized endpoint fails, it automatically falls back to original TTS
- All errors are logged with detailed context
- Performance targets are tracked and reported

## 📈 Monitoring in Production

Set up monitoring for:
- Average TTS generation time
- Cache hit rate percentage  
- Performance target achievement rate
- Error rates and fallback usage

Target alerts:
- Generation time > 2.5s consistently
- Cache hit rate < 30%
- High error rates in optimized endpoint
