# Vercel Environment Variables Reference

## Supabase Connection Variables

When you connect Supabase through Vercel, it automatically creates these environment variables:

### Primary Database URLs

1. **`DATABASE_POSTGRES_URL`** ⭐ (Recommended)
   - Pooled PostgreSQL connection
   - Best for serverless functions
   - Handles connection limits automatically
   - **Our code uses this automatically**

2. **`DATABASE_SUPABASE_URL`**
   - Supabase-specific connection string
   - Also works, but `DATABASE_POSTGRES_URL` is preferred

3. **`DATABASE_POSTGRES_URL_NON_POOLING`**
   - Direct PostgreSQL connection (no pooling)
   - Less ideal for serverless (can hit connection limits)
   - Fallback option

4. **`DATABASE_POSTGRES_PRISMA_URL`**
   - Prisma-specific format
   - Not used by our code

### Supabase-Specific Variables

5. **`DATABASE_SUPABASE_PUBLISHABLE_KEY`**
   - Supabase public API key
   - For client-side Supabase SDK (if needed later)

6. **`NEXT_PUBLIC_DATABASE_SUPABASE_URL`**
   - Public Supabase URL (for client-side)
   - Not used by our backend

7. **`DATABASE_SUPABASE_JWT_SECRET`**
   - Supabase JWT secret
   - For Supabase Auth (if using Supabase Auth later)

8. **`DATABASE_POSTGRES_USER`**
   - PostgreSQL username
   - Not needed (included in connection string)

## How Our Code Handles This

The `Database` class automatically checks for these variables in order:

1. `DATABASE_URL` (if manually set)
2. `DATABASE_POSTGRES_URL` ⭐ (Vercel pooled - preferred)
3. `DATABASE_SUPABASE_URL` (Vercel Supabase)
4. `DATABASE_POSTGRES_URL_NON_POOLING` (fallback)

**You don't need to do anything** - the code automatically uses the best available connection!

## Verification

After connecting Supabase, verify in Vercel:
- Settings → Environment Variables
- You should see `DATABASE_POSTGRES_URL` with a connection string
- Our code will automatically use it

## Manual Override

If you want to use a specific variable, you can set `DATABASE_URL` manually:
- It will take precedence over the others
- Useful for testing or custom configurations

