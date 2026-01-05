# Local Setup Guide

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment (if not exists)
python3 -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate  # On Windows

# Install all dependencies
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Create a `.env` file in the project root:

```bash
# Generate SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Add to .env file:
SECRET_KEY=<paste-generated-key-here>
```

The `.env` file is already in `.gitignore`, so it won't be committed.

### 3. Run the Application

```bash
# Make sure venv is activated
source venv/bin/activate

# Run the app
python3 app_new.py
```

The app will start on `http://localhost:5001`

### 4. Test It Works

```bash
# Test endpoint (no dependencies)
curl http://localhost:5001/api/test

# Health check
curl http://localhost:5001/api/health

# Or open in browser
open http://localhost:5001
```

## Run Test Script

To verify everything is set up correctly:

```bash
# Activate venv first
source venv/bin/activate

# Run test script
python3 test_local.py
```

This will test:
- ✅ Flask imports
- ✅ App imports
- ✅ Route registration
- ✅ API endpoints

## Troubleshooting

### "ModuleNotFoundError: No module named 'flask_cors'"

**Fix:**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### "Port already in use"

**Fix:**
```bash
# Kill process on port 5001
lsof -ti:5001 | xargs kill -9

# Or change port in app_new.py
```

### Database Connection Issues

For local development, the app will use SQLite by default (stored in `data/focalprompt.db`).

If you want to use PostgreSQL locally:
1. Install PostgreSQL
2. Create a database
3. Add to `.env`:
   ```
   DATABASE_URL=postgresql://user:password@localhost:5432/focalprompt
   ```

## Development Workflow

1. **Make changes** to code
2. **Test locally** with `python3 app_new.py`
3. **Commit and push** to trigger Vercel deployment
4. **Check Vercel logs** if deployment fails

## Next Steps

- ✅ Local setup complete
- 🔄 Test endpoints work
- 🚀 Ready to deploy to Vercel

