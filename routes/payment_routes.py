#!/usr/bin/env python3
"""
Payment route handlers.

Handles Stripe checkout, customer portal, and webhooks.
"""

from flask import Blueprint, request, jsonify
import os
import stripe
from services.stripe_service import StripeService
from services.database import Database
from middleware.auth import require_auth

payment_bp = Blueprint('payment', __name__)

# Initialize services
stripe_service = StripeService()
db = Database()


@payment_bp.route('/api/payment/create-checkout', methods=['POST'])
@require_auth
def create_checkout():
    """Create Stripe checkout session."""
    try:
        data = request.json
        tier = data.get('tier')
        
        if not tier or tier not in ['starter', 'professional', 'enterprise']:
            return jsonify({'error': 'Invalid tier'}), 400
        
        base_url = os.getenv('BASE_URL', request.host_url.rstrip('/'))
        
        result = stripe_service.create_checkout_session(
            request.user['id'],
            tier,
            base_url
        )
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@payment_bp.route('/api/payment/portal', methods=['POST'])
@require_auth
def create_portal():
    """Create Stripe customer portal session."""
    try:
        base_url = os.getenv('BASE_URL', request.host_url.rstrip('/'))
        
        result = stripe_service.create_portal_session(
            request.user['id'],
            base_url
        )
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@payment_bp.route('/api/payment/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks."""
    try:
        payload = request.data
        signature = request.headers.get('Stripe-Signature')
        
        if not signature:
            return jsonify({'error': 'Missing signature'}), 400
        
        # Handle webhook using service
        result = stripe_service.handle_webhook(payload, signature)
        
        # Also handle payment_intent events for pay-as-you-go
        if 'error' not in result:
            try:
                event = stripe.Webhook.construct_event(
                    payload,
                    signature,
                    stripe_service.webhook_secret
                )
                
                if event['type'] == 'payment_intent.succeeded':
                    payment_intent = event['data']['object']
                    db.update_charge_status(payment_intent.id, 'succeeded')
                elif event['type'] == 'payment_intent.payment_failed':
                    payment_intent = event['data']['object']
                    db.update_charge_status(payment_intent.id, 'failed')
            except:
                pass  # Let service handle it
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

