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

## Testing

After setting up, you can test the gateway by making a request. The error should change from 404 to a different error (or work if everything is correct).

