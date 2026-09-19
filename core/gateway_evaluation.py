"""Python adapter for Gateway's experimental AI SDK evaluation v4 transport.

Wire contract: vercel/ai packages/gateway/src/gateway-evaluation-model.ts.
This is separate from the OpenAI-compatible chat API, which cannot run Jev.
"""

import os

import requests


JEV_MODEL = 'typesafe-ai/jev'
EVALUATION_URL = 'https://ai-gateway.vercel.sh/v4/ai/evaluation-model'


class EvaluationError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


class GatewayEvaluation:
    def evaluate(self, state, questions):
        key = os.getenv('AI_GATEWAY_API_KEY')
        if not key:
            raise EvaluationError('Jev requires a server-side AI Gateway API key.', 503)
        try:
            response = requests.post(
                EVALUATION_URL,
                headers={
                    'Authorization': f'Bearer {key}',
                    'Content-Type': 'application/json',
                    'ai-gateway-protocol-version': '0.0.1',
                    'ai-gateway-auth-method': 'api-key',
                    'ai-evaluation-model-specification-version': '4',
                    'ai-model-id': JEV_MODEL,
                },
                json={'state': state, 'questions': questions,
                      'providerOptions': {'gateway': {'zeroDataRetention': True}}},
                timeout=(10, 60),
            )
        except requests.Timeout:
            raise EvaluationError('Jev timed out. Retry the unfinished decision.', 504) from None
        except requests.RequestException:
            raise EvaluationError('Could not connect to Jev through AI Gateway.', 503) from None
        if response.status_code != 200:
            # Never expose or log upstream bodies: they may echo the scenario or key.
            status = response.status_code
            public_status = status if status in (401, 403, 429, 503, 504) else 502
            raise EvaluationError(f'Jev evaluation was rejected by AI Gateway (HTTP {status}).', public_status)
        try:
            result = response.json()
        except ValueError:
            raise EvaluationError('Jev returned an invalid evaluation response.') from None
        if not isinstance(result, dict) or not isinstance(result.get('answers'), dict):
            raise EvaluationError('Jev returned no typed answers.')
        # Retain experiment provenance without returning HTTP headers/credentials.
        return {key: result[key] for key in
                ('answers', 'usage', 'providerMetadata', 'rounding', 'warnings') if key in result}
