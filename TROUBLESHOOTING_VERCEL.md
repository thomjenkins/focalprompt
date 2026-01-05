# Troubleshooting Vercel 500 Errors

## Common Issues and Fixes

### 1. Module Import Errors

**Error:** `ModuleNotFoundError: No module named 'flask_cors'`

**Fix:**
- Verify `requirements.txt` has all dependencies
- Check Vercel build logs to see if pip install succeeded
- Ensure package names match (e.g., `flask-cors` not `flask_cors`)

### 2. Database Initialization Errors

**Error:** Database fails to initialize on import

**Symptoms:**
- Function crashes immediately
- Error in logs about database connection

**Fix:**
- Make sure `DATABASE_POSTGRES_URL` is set in Vercel environment variables
- Database initialization is now deferred (won't crash on import)
- Check Vercel logs for specific database errors

### 3. Missing Environment Variables

**Error:** `SECRET_KEY` or other required variables missing

**Fix:**
- Go to Vercel Dashboard → Settings → Environment Variables
- Add `SECRET_KEY` (required)
- Verify `DATABASE_POSTGRES_URL` exists (from Supabase connection)

### 4. Import Errors in Routes

**Error:** Routes fail to import

**Check:**
- All route files are committed to git
- No circular imports
- All dependencies in `requirements.txt`

## Debugging Steps

### 1. Check Vercel Logs

1. Go to Vercel Dashboard → Your Project
2. Click on the failed deployment
3. Go to "Functions" tab
4. Click "View Logs"
5. Look for Python traceback errors

### 2. Test Locally

```bash
# Test imports
python3 -c "from app_new import app; print('OK')"

# Test API entry point
python3 -c "from api.index import handler; print('OK')"
```

### 3. Verify Environment Variables

```bash
# In Vercel Dashboard, check:
- SECRET_KEY is set
- DATABASE_POSTGRES_URL is set (from Supabase)
```

### 4. Check Build Logs

In Vercel deployment logs, verify:
- ✅ Dependencies installed successfully
- ✅ Build completed
- ❌ Function invocation failed (this is where the error is)

## Quick Fixes

### If Database is the Issue

The database service now:
- ✅ Defers initialization (doesn't crash on import)
- ✅ Retries connection on first use
- ✅ Falls back gracefully if database unavailable

### If Import is the Issue

The API entry point now:
- ✅ Has error handling for import failures
- ✅ Returns helpful error messages
- ✅ Logs errors to stderr (visible in Vercel logs)

## Next Steps

1. **Check Vercel Function Logs** - This will show the exact error
2. **Verify Environment Variables** - Make sure all required vars are set
3. **Test Health Endpoint** - `/api/health` should work even without database

## Getting More Info

To see the actual error, check Vercel logs:
- Dashboard → Deployments → Failed deployment → Functions → View Logs

The error message will tell you exactly what's failing.

