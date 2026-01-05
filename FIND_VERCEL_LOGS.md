# How to Find Vercel Runtime Logs

## Step-by-Step Guide

### Option 1: From Deployment Page (Easiest)

1. **Go to Vercel Dashboard** → Your Project (`focalprompt`)
2. **Click on the deployment** that shows "500 (Internal Server Error)"
3. **Look for the "Runtime Logs" card** (it's a large card on the deployment page)
4. **Click "View Logs"** or the card itself
5. **You'll see the Python traceback** with the exact error

### Option 2: From Project Overview

1. **Go to Vercel Dashboard** → Your Project
2. **Click "Logs" tab** at the top (next to "Deployments", "Settings", etc.)
3. **Filter by your deployment** or look for recent errors
4. **Click on an error** to see details

### Option 3: Real-time Logs

1. **Go to Vercel Dashboard** → Your Project
2. **Click "Logs" tab**
3. **Click "Real-time"** to see logs as they happen
4. **Visit your site** (`https://www.focalprompt.com`) to trigger the error
5. **Watch the logs appear** in real-time

## What to Look For

The logs will show:
- `🔄 Attempting to import app_new...` - Shows import started
- `✅ App imported successfully` - Import worked
- `❌ ERROR: ...` - The actual error
- Full Python traceback - Shows exactly where it failed

## Common Error Patterns

### Import Error
```
❌ ImportError: Failed to import app_new
ModuleNotFoundError: No module named 'X'
```
**Fix:** Check `requirements.txt` has all dependencies

### Route Registration Error
```
Error registering assessment_bp: ...
```
**Fix:** Check that route file exists and imports are correct

### Database Error
```
PostgreSQL connection pool not available
```
**Fix:** Verify `DATABASE_POSTGRES_URL` is set in environment variables

## Alternative: Check via API

If the app partially loads, you can also check:

```bash
# Test endpoint (should work even if app has issues)
curl https://www.focalprompt.com/api/test

# Diagnostic endpoint (shows module status)
curl https://www.focalprompt.com/api/diagnostic

# Health check
curl https://www.focalprompt.com/api/health
```

These endpoints will return JSON with error details if something is wrong.

