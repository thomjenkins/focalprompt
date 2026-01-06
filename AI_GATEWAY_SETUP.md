# Vercel AI Gateway Setup Guide

## The Error You're Seeing

If you see: `"The deployment could not be found on Vercel"` (404 error), it means the AI Gateway API key is incorrect or the gateway isn't properly configured.

## How to Set Up Vercel AI Gateway

### Step 1: Create AI Gateway in Vercel Dashboard

1. Go to your Vercel project dashboard
2. Navigate to **Settings** → **AI Gateway** (or **Storage** → **AI Gateway**)
3. Click **Create Gateway** or **Enable AI Gateway**
4. This will create a gateway for your project

### Step 2: Get Your Gateway API Key

1. In the AI Gateway settings, you'll see your **Gateway API Key**
2. Copy this key - it should look like: `gateway_xxxxx...`

### Step 3: Set Environment Variable

In your Vercel project settings:

1. Go to **Settings** → **Environment Variables**
2. Add a new variable:
   - **Name**: `AI_GATEWAY_API_KEY`
   - **Value**: Your gateway API key from Step 2
   - **Environment**: Production, Preview, Development (select all)

### Step 4: Verify Gateway URL

The default gateway URL is: `https://gateway.vercel.ai/v1`

If you need a custom URL, you can set:
- **Name**: `AI_GATEWAY_URL`
- **Value**: Your custom gateway URL

## Important Notes

- The AI Gateway API key is **different** from your Vercel API token
- The gateway must be created in the same Vercel project where your app is deployed
- The gateway API key is project-specific

## Troubleshooting

### Error: "The deployment could not be found"
- Verify the `AI_GATEWAY_API_KEY` is set correctly in Vercel
- Make sure the gateway is created in the same Vercel project
- Check that the gateway is active/enabled in the dashboard

### Error: "Authentication failed" (401)
- Verify the API key is correct
- Make sure there are no extra spaces or characters
- Try regenerating the gateway API key

### Error: "Access denied" (403)
- Check that the gateway API key has the correct permissions
- Verify the gateway is enabled for your project

## Testing the Gateway

### Option 1: Test with TypeScript Script (Recommended)

The `gateway.ts` file in the root directory can be used to test your gateway connection:

1. **Navigate to the root directory:**
   ```bash
   cd /Users/thomasjenkins/FocalPrompt
   ```

2. **Make sure you have the required packages:**
   ```bash
   cd demo
   pnpm install @vercel/ai dotenv tsx
   cd ..
   ```

3. **Create a `.env` file in the root directory** (if you don't have one):
   ```bash
   echo "AI_GATEWAY_API_KEY=your_gateway_key_here" > .env
   ```
   Replace `your_gateway_key_here` with your actual gateway API key from Step 2.

4. **Run the test script:**
   ```bash
   cd demo
   pnpm tsx ../gateway.ts
   ```

   Or from the root directory:
   ```bash
   pnpm --dir demo tsx gateway.ts
   ```

5. **Expected output:**
   - If successful: You'll see the AI-generated text stream, followed by token usage and finish reason
   - If there's an error: You'll see a clear error message

### Option 2: Test via Your Python Application

1. **Set the environment variable locally** (for testing):
   ```bash
   export AI_GATEWAY_API_KEY="your_gateway_key_here"
   ```

2. **Run your Flask app:**
   ```bash
   python app_new.py
   ```

3. **Try the "Auto-Detect Foci" feature** - if the gateway is configured correctly, it should work without the 404 error.

### Option 3: Test with curl

```bash
curl https://gateway.vercel.ai/v1/chat/completions \
  -H "Authorization: Bearer YOUR_GATEWAY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Common Issues

### File Not Found Error
If you see `Cannot find module '/Users/thomasjenkins/FocalPrompt/demo/gateway.ts'`:
- The script is in the root directory, not the `demo` directory
- Run: `pnpm --dir demo tsx gateway.ts` from the root, or
- Copy `gateway.ts` to the `demo` directory, or
- Run from root: `cd /Users/thomasjenkins/FocalPrompt && pnpm --dir demo tsx gateway.ts`

### Still Getting 404 Error
- Verify the gateway is actually created in your Vercel project dashboard
- Check that the API key is correct (no extra spaces, complete key)
- Make sure you're using the gateway API key, not your Vercel account token
- The gateway must be in the same Vercel project where your app is deployed

