# Vercel Deployment Guide

## Issues Fixed

1. **Created `vercel.json`** - Configuration for Flask app
2. **Created `api/index.py`** - Vercel serverless function entry point
3. **Updated database service** - Handles Vercel's read-only filesystem by using `/tmp`

## Important Notes

### SQLite Limitation on Vercel

⚠️ **SQLite won't work properly on Vercel** because:
- Vercel's filesystem is read-only (except `/tmp`)
- `/tmp` is ephemeral and cleared between deployments
- Database will be lost on each deployment

### Solutions

**Option 1: Use PostgreSQL (Recommended)**
- Set up Vercel Postgres or external PostgreSQL
- Update `services/database.py` to use PostgreSQL connection string
- Use `DATABASE_URL` environment variable

**Option 2: Use External Database Service**
- Supabase (free tier available)
- PlanetScale
- Railway
- Render

**Option 3: Disable Auth Temporarily**
- For MVP, you can disable authentication
- App will work without user accounts

## Deployment Steps

### 1. Commit All Changes

```bash
git add .
git commit -m "Add SaaS features and Vercel configuration"
git push origin main
```

### 2. Set Environment Variables in Vercel

Go to Vercel Dashboard → Your Project → Settings → Environment Variables:

**Required:**
- `SECRET_KEY` - Generate with: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`

**Optional (for full SaaS):**
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_STARTER`
- `STRIPE_PRICE_PROFESSIONAL`
- `STRIPE_PRICE_ENTERPRISE`
- `BASE_URL` - Your Vercel URL

**Optional (for LLM):**
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`

### 3. Deploy

Vercel will auto-deploy on push, or:
```bash
vercel --prod
```

## Database Migration to PostgreSQL

To use PostgreSQL instead of SQLite:

1. **Set up Vercel Postgres:**
   - Vercel Dashboard → Storage → Create Database → Postgres
   - Copy connection string

2. **Update `services/database.py`:**
   ```python
   import psycopg2
   from urllib.parse import urlparse
   
   # Use DATABASE_URL if available (PostgreSQL)
   database_url = os.getenv('DATABASE_URL')
   if database_url:
       # Use PostgreSQL
   else:
       # Fall back to SQLite
   ```

3. **Add to requirements.txt:**
   ```
   psycopg2-binary>=2.9.0
   ```

4. **Update environment variables:**
   - Add `DATABASE_URL` from Vercel Postgres

## Troubleshooting

### Error: FUNCTION_INVOCATION_FAILED

**Common causes:**
1. Missing environment variables
2. Database initialization failing
3. Import errors
4. Missing dependencies

**Check Vercel logs:**
- Vercel Dashboard → Your Project → Deployments → Click deployment → Functions → View logs

### Database Errors

If you see database errors:
- Database is trying to write to read-only filesystem
- Solution: Use PostgreSQL or disable auth features

### Import Errors

If imports fail:
- Check `requirements.txt` has all dependencies
- Verify Python version (3.12)
- Check that all files are committed to git

## Current Status

✅ **Working:**
- Flask app structure
- Vercel configuration
- Basic routes

⚠️ **Needs Setup:**
- Database (PostgreSQL recommended)
- Environment variables
- Stripe (if using payments)

## Quick Test

After deployment, test:
```bash
curl https://your-app.vercel.app/api/health
```

Should return:
```json
{"status": "ok", "api_key_set": false}
```

