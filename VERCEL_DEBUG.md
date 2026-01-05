# Vercel 500 Error Debugging Guide

## Current Status

The app is getting a 500 error on Vercel. Here's what we've fixed and how to debug:

## Fixes Applied

1. ✅ **Database initialization deferred** - Won't crash on import
2. ✅ **Error handling in API entry point** - Better error messages
3. ✅ **PostgreSQL connection retry** - Retries if pool fails
4. ✅ **Health check improved** - Shows database status

## How to Debug

### Step 1: Check Vercel Function Logs

1. Go to Vercel Dashboard → Your Project
2. Click on the failed deployment
3. Click "Functions" tab
4. Click "View Logs" or the function name
5. Look for Python traceback

**This will show the exact error!**

### Step 2: Verify Environment Variables

In Vercel Dashboard → Settings → Environment Variables, check:

**Required:**
- `SECRET_KEY` - Must be set (generate with: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`)

**Database (should be auto-created by Supabase):**
- `DATABASE_POSTGRES_URL` - Should exist if Supabase is connected
- `DATABASE_SUPABASE_URL` - Alternative

### Step 3: Test Health Endpoint

After deployment, test:
```bash
curl https://your-app.vercel.app/api/health
```

Should return:
```json
{
  "status": "ok",
  "api_key_set": false,
  "database_configured": true,
  "secret_key_set": true
}
```

## Common Causes

### 1. Missing SECRET_KEY
**Error:** App crashes on startup
**Fix:** Add `SECRET_KEY` to Vercel environment variables

### 2. Database Connection Failing
**Error:** Database initialization errors
**Fix:** 
- Verify `DATABASE_POSTGRES_URL` is set
- Check Supabase connection in Vercel
- Database now defers initialization (won't crash on import)

### 3. Import Errors
**Error:** `ModuleNotFoundError`
**Fix:**
- Check `requirements.txt` has all packages
- Verify build logs show successful pip install

### 4. Route Import Errors
**Error:** Blueprint import fails
**Fix:**
- Check all route files are committed
- Verify no circular imports

## What to Check in Logs

Look for these in Vercel function logs:

1. **Import errors:**
   ```
   ModuleNotFoundError: No module named '...'
   ```

2. **Database errors:**
   ```
   PostgreSQL connection pool not available
   SQLite connection failed
   ```

3. **Initialization errors:**
   ```
   Failed to create PostgreSQL pool
   Database initialization deferred
   ```

## Quick Test

After fixing, the health endpoint should work:
```bash
curl https://your-app.vercel.app/api/health
```

If this works, the app is running! Then test other endpoints.

## Next Steps

1. **Check Vercel logs** - This is the most important step!
2. **Verify environment variables** - Especially `SECRET_KEY`
3. **Test health endpoint** - Should work even without database
4. **Check build logs** - Make sure dependencies installed

The error handler in `api/index.py` will now show helpful error messages if imports fail.

