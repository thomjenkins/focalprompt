# Supabase Database Setup for FocalPrompt

## Quick Setup

### 1. Connect Supabase in Vercel

1. Go to Vercel Dashboard → Your Project → Storage
2. Click "Browse Storage" → Select "Supabase"
3. In "Custom Prefix" field, enter: `DATABASE` (this creates `DATABASE_URL`)
4. Select environments (Development, Preview, Production)
5. Click "Connect"
6. Vercel will automatically:
   - Create a Supabase project (if you don't have one)
   - Add multiple environment variables (see below)
   - Set up the connection

### 2. Verify Environment Variables

After connecting, check Vercel Dashboard → Settings → Environment Variables:

**You should see:**
- `DATABASE_POSTGRES_URL` ⭐ (pooled connection - our code uses this)
- `DATABASE_SUPABASE_URL`
- `DATABASE_POSTGRES_URL_NON_POOLING`
- `DATABASE_SUPABASE_PUBLISHABLE_KEY`
- And several others

**Our code automatically detects and uses `DATABASE_POSTGRES_URL`** (the best one for serverless)

### 3. Deploy

The database service will automatically:
- Detect `DATABASE_URL`
- Use PostgreSQL instead of SQLite
- Create tables on first run

## Manual Setup (Alternative)

If you prefer to set up Supabase manually:

### 1. Create Supabase Project

1. Go to https://supabase.com
2. Create a new project
3. Wait for database to be provisioned

### 2. Get Connection String

**Note:** If you connected Supabase through Vercel's storage browser, this is already done! Vercel automatically creates:
- `DATABASE_POSTGRES_URL` (pooled - recommended)
- `DATABASE_SUPABASE_URL`
- Other Supabase variables

**If setting up manually:**
1. Supabase Dashboard → Project Settings → Database
2. Find "Connection string" → "URI"
3. Copy the connection string (starts with `postgresql://`)

### 3. Add to Vercel (Manual Setup Only)

**If you connected through Vercel, skip this step!**

1. Vercel Dashboard → Settings → Environment Variables
2. Add:
   - Name: `DATABASE_POSTGRES_URL` (or `DATABASE_URL`)
   - Value: Your Supabase connection string
   - Environment: Production, Preview, Development

### 4. Update Connection String (Important!)

Supabase connection strings include a password. You need to:
1. Replace `[YOUR-PASSWORD]` with your actual database password
2. Or use the "Connection pooling" string (recommended for serverless)

**Connection Pooling (Recommended):**
- Use port `6543` instead of `5432`
- Better for serverless functions
- Handles connection limits better

Example:
```
postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:6543/postgres?pgbouncer=true
```

## Database Tables

The following tables will be created automatically:

1. **users** - User accounts
2. **sessions** - Authentication sessions
3. **usage** - API usage tracking

## Testing the Connection

After deployment, test with:

```bash
curl https://your-app.vercel.app/api/health
```

Then try registering a user:
```bash
curl -X POST https://your-app.vercel.app/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "test123456"}'
```

## Troubleshooting

### Connection Errors

**Error: "connection refused"**
- Check `DATABASE_URL` is set correctly
- Verify Supabase project is active
- Check if using connection pooling port (6543)

**Error: "password authentication failed"**
- Verify password in connection string
- Check Supabase project settings

**Error: "relation does not exist"**
- Tables should be created automatically
- Check Vercel function logs for initialization errors

### Performance

- Use connection pooling (port 6543) for better performance
- Supabase free tier: 500 MB database, 2 GB bandwidth
- Upgrade if you need more capacity

## Migration from SQLite

If you were using SQLite locally:
1. Data won't automatically migrate
2. Users need to re-register
3. Usage history will start fresh

This is expected - SQLite and PostgreSQL are separate databases.

## Security Notes

- Never commit `DATABASE_URL` to git
- Use Vercel environment variables
- Supabase connection strings include passwords
- Keep them secret!

## Next Steps

1. ✅ Connect Supabase in Vercel
2. ✅ Verify `DATABASE_URL` is set
3. ✅ Deploy and test
4. ✅ Register a test user
5. ✅ Verify data persists across deployments

Your database is now production-ready! 🎉

