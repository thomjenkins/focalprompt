import { streamText } from 'ai';
import 'dotenv/config';

async function main() {
  // Check if API key is set
  if (!process.env.AI_GATEWAY_API_KEY) {
    console.error('Error: AI_GATEWAY_API_KEY environment variable not set');
    console.error('Please set it in your .env file or environment');
    process.exit(1);
  }

  console.log('Testing Vercel AI Gateway...');
  console.log('API Key:', process.env.AI_GATEWAY_API_KEY.substring(0, 20) + '...');
  console.log('');

  const result = streamText({
    model: 'openai/gpt-4o-mini', // Using a model that exists
    prompt: 'Invent a new holiday and describe its traditions.',
    apiKey: process.env.AI_GATEWAY_API_KEY,
    baseURL: 'https://gateway.vercel.ai/v1',
  });

  for await (const textPart of result.textStream) {
    process.stdout.write(textPart);
  }

  console.log();
  console.log('');
  console.log('Token usage:', await result.usage);
  console.log('Finish reason:', await result.finishReason);
  console.log('');
  console.log('✅ Gateway test successful!');
}

main().catch((error) => {
  console.error('❌ Gateway test failed:');
  console.error(error.message);
  if (error.response) {
    console.error('Status:', error.response.status);
    console.error('Response:', error.response.data);
  }
  process.exit(1);
});