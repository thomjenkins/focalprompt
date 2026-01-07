# Vercel Timeout Limits and Long-Running Tasks

## Problem

Vercel serverless functions have hard execution time limits:
- **Free/Hobby**: 10 seconds
- **Pro**: 60 seconds
- **Enterprise**: 300 seconds (5 minutes)
- **Fluid Compute** (paid plans): up to 14 minutes

LLM tasks (especially with slow models like `grok-4`) can easily exceed these limits, causing:
1. **Function timeouts**: Request is killed mid-execution
2. **Token waste**: If a request times out after consuming tokens, retrying wastes money
3. **Poor user experience**: Long waits with no feedback

## Solutions

### 1. Streaming Responses (Recommended)

Use streaming to get partial results and avoid timeouts:

```python
# In AI Gateway provider
def chat_completion_stream(self, messages, model, ...):
    payload = {..., 'stream': True}
    response = requests.post(url, json=payload, stream=True, timeout=timeout)
    for line in response.iter_lines():
        # Process streaming chunks
        yield parse_chunk(line)
```

**Benefits:**
- Get partial results immediately
- Avoid function timeouts (streaming keeps connection alive)
- Better UX with progress indicators
- No token waste (can save partial results)

### 2. Background Job Queue

For very long tasks (>5 minutes), use background processing:

**Option A: Vercel Cron + External Worker**
- Use Vercel Cron to trigger background jobs
- Process jobs in external worker (e.g., Railway, Render, Fly.io)
- Store results in database
- Poll for completion from frontend

**Option B: Queue Service**
- Use a queue service (e.g., Inngest, Trigger.dev, BullMQ)
- Queue long-running tasks
- Process asynchronously
- Notify frontend when complete

### 3. Task Chunking

Break large tasks into smaller chunks:

```python
# Instead of processing 1000 items at once
for batch in chunks(items, size=10):
    process_batch(batch)
    yield progress_update()
```

### 4. Model Selection

Use faster models for time-sensitive tasks:
- `gpt-4o-mini` instead of `gpt-4o` for simple tasks
- `gemini-2.5-flash` instead of `gemini-2.5-pro` for quick responses
- Reserve slow models (`grok-4`, `o3`) for non-time-sensitive tasks

### 5. Avoid Retries on Timeout

**Critical**: Don't retry requests that timed out after consuming tokens.

```python
# BAD: Retries after timeout wastes tokens
except Timeout:
    retry()  # ❌ Wastes tokens if first request already consumed them

# GOOD: Only retry connection errors, not read timeouts
except ConnectionError:
    retry()  # ✅ Safe to retry
except Timeout:
    raise  # ❌ Don't retry - would waste tokens
```

## Current Implementation

Our current implementation:
- ✅ Reduced retries to 1 (only for connection errors)
- ✅ Don't retry on read timeouts (avoids token waste)
- ✅ Increased timeout to 120s for slow models
- ⚠️ **TODO**: Add streaming support for long responses
- ⚠️ **TODO**: Add background job queue for very long tasks

## Recommendations

1. **Short tasks (<60s)**: Current implementation is fine
2. **Medium tasks (60s-5min)**: Implement streaming
3. **Long tasks (>5min)**: Use background job queue

## Example: Streaming Implementation

```python
@assessment_bp.route('/api/assess-stream', methods=['POST'])
@stream_with_context
def assess_stream():
    def generate():
        try:
            # Stream LLM response
            for chunk in assessor.stream_assess(prompt, output, foci):
                yield f"data: {json.dumps(chunk)}\n\n"
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')
```

