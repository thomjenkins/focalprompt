# Troubleshooting Guide

## Server Not Starting

1. **Check if port 5000 is in use:**
   ```bash
   lsof -ti:5000
   ```
   If a process is found, kill it:
   ```bash
   lsof -ti:5000 | xargs kill
   ```

2. **Make sure virtual environment is activated:**
   ```bash
   source venv/bin/activate
   ```

3. **Check if dependencies are installed:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Verify API key is set:**
   ```bash
   echo $OPENAI_API_KEY
   ```
   If empty, set it:
   ```bash
   export OPENAI_API_KEY="your-key-here"
   ```

## Browser Shows 403 Error

1. **Use 127.0.0.1 instead of localhost:**
   - Try: `http://127.0.0.1:5000`
   - Instead of: `http://localhost:5000`

2. **Check server is running:**
   ```bash
   curl http://127.0.0.1:5000
   ```
   Should return HTML content.

## API Errors

1. **"OPENAI_API_KEY not set" error:**
   - Make sure you've set the environment variable
   - Restart the server after setting it
   - Check with: `echo $OPENAI_API_KEY`

2. **"Module not found" errors:**
   - Activate virtual environment: `source venv/bin/activate`
   - Reinstall dependencies: `pip install -r requirements.txt`

## Features Not Working

1. **Auto-Detect Foci not working:**
   - Check browser console for errors (F12)
   - Verify API key is set
   - Check server logs for errors

2. **Generate Output not working:**
   - Same as above
   - Make sure you have a prompt entered

3. **Assess Focus not working:**
   - Make sure both prompt and output are filled
   - Check browser console for detailed error messages

## Quick Test

Test if everything is working:

```bash
# 1. Activate venv
source venv/bin/activate

# 2. Check API key
echo $OPENAI_API_KEY

# 3. Start server
python app.py

# 4. In another terminal, test the API
curl -X POST http://127.0.0.1:5000/api/health
```

## Still Having Issues?

1. Check server logs in the terminal where you ran `python app.py`
2. Open browser developer tools (F12) and check the Console tab
3. Check the Network tab to see if API requests are failing
4. Make sure you're using the correct URL: `http://127.0.0.1:5000`


