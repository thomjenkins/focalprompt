#!/usr/bin/env python3
"""
Payment route handlers.

Handles Stripe checkout, customer portal, and webhooks.
"""

from flask import Blueprint, request, jsonify
import os
from services.database import Database
from middleware.auth import require_auth

payment_bp = Blueprint('payment', __name__)

# Lazy initialization - only create services when needed
_stripe_service = None
_db = None

def get_stripe_service():
    """Get StripeService instance (lazy initialization)."""
    global _stripe_service
    if _stripe_service is None:
        try:
            import stripe
            from services.stripe_service import StripeService
            _stripe_service = StripeService()
        except ImportError:
            raise ImportError("stripe package not installed. Install with: pip install stripe")
    return _stripe_service

def get_db():
    """Get database instance (lazy initialization)."""
    global _db
    if _db is None:
        _db = Database()
    return _db


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
        
        stripe_service = get_stripe_service()
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
        
        stripe_service = get_stripe_service()
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
        stripe_service = get_stripe_service()
        result = stripe_service.handle_webhook(payload, signature)
        
        # Also handle payment_intent events for pay-as-you-go
        if 'error' not in result:
            try:
                import stripe
                event = stripe.Webhook.construct_event(
                    payload,
                    signature,
                    stripe_service.webhook_secret
                )
                
                if event['type'] == 'payment_intent.succeeded':
                    payment_intent = event['data']['object']
                    get_db().update_charge_status(payment_intent.id, 'succeeded')
                elif event['type'] == 'payment_intent.payment_failed':
                    payment_intent = event['data']['object']
                    get_db().update_charge_status(payment_intent.id, 'failed')
            except:
                pass  # Let service handle it
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

