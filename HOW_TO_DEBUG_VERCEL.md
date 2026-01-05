# How to Debug Vercel 500 Errors

## Step 1: Check Vercel Function Logs (CRITICAL)

This is the **most important step** - it will show you the exact error:

1. Go to **Vercel Dashboard** → Your Project (`focalprompt`)
2. Click on the **failed deployment** (the one showing 500 error)
3. Click the **"Functions"** tab
4. Click **"View Logs"** or click on the function name
5. **Look for the Python traceback** - this shows exactly what's failing

The logs will show something like:
```
ERROR: Failed to import app: <error message>
Traceback (most recent call last):
  File "api/index.py", line 13, in <module>
    from app_new import app
  ...
```

## Step 2: Common Errors and Fixes

### Error: "ModuleNotFoundError: No module named 'flask_cors'"

**Fix:**
- Check `requirements.txt` has `flask-cors>=4.0.0`
- Verify Vercel build logs show successful pip install
- If missing, add to `requirements.txt` and redeploy

### Error: "PostgreSQL connection pool not available"

**Fix:**
- Verify `DATABASE_POSTGRES_URL` is set in Vercel environment variables
- Check Supabase connection in Vercel Storage
- Database now initializes lazily (won't crash on import)

### Error: "SECRET_KEY not set"

**Fix:**
- Add `SECRET_KEY` to Vercel environment variables
- Generate with: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`

### Error: Import errors in routes

**Fix:**
- Check all route files are committed to git
- Verify no circular imports
- Check Vercel logs for specific import error

## Step 3: Test Endpoints

After deployment, test these endpoints:

### 1. Test Endpoint (No dependencies)
```bash
curl https://www.focalprompt.com/api/test
```
Should return: `{"status": "ok", "message": "App is running"}`

### 2. Health Check
```bash
curl https://www.focalprompt.com/api/health
```
Shows status of app, database, and environment variables

## Step 4: Verify Environment Variables

In Vercel Dashboard → Settings → Environment Variables:

**Required:**
- ✅ `SECRET_KEY` - Must be set

**Database (Auto-created by Supabase):**
- ✅ `DATABASE_POSTGRES_URL` - Should exist
- ✅ `DATABASE_SUPABASE_URL` - Also exists

**Optional:**
- `BASE_URL` - Your Vercel URL
- `OPENAI_API_KEY` - For LLM features

## What We've Fixed

1. ✅ **Lazy database initialization** - Won't crash on import
2. ✅ **Error handler in API entry point** - Shows helpful errors
3. ✅ **Test endpoint** - `/api/test` works without any dependencies
4. ✅ **Better error messages** - Logs to stderr (visible in Vercel logs)

## Next Steps

1. **Check Vercel Function Logs** ← **DO THIS FIRST**
2. **Look for the Python traceback** - It will tell you exactly what's wrong
3. **Fix the specific error** based on the traceback
4. **Redeploy** and test again

## Quick Commands

```bash
# Push latest fixes
git push origin main

# Test after deployment
curl https://www.focalprompt.com/api/test
curl https://www.focalprompt.com/api/health
```

The error logs will show you exactly what's failing! 🔍

