#!/usr/bin/env python3
"""
Credit management route handlers.

Provides endpoints for viewing credit balance and topping up.
"""

from flask import Blueprint, request, jsonify
from services.database import Database
from services.billing_service import BillingService
from services.stripe_service import StripeService
from middleware.auth import require_auth
import os

credit_bp = Blueprint('credit', __name__)

# Initialize services
db = Database()
billing_service = BillingService(db)
stripe_service = StripeService()


@credit_bp.route('/api/credit/balance', methods=['GET'])
@require_auth
def get_credit_balance():
    """Get user's current credit balance."""
    try:
        balance = billing_service.get_user_credit_balance(request.user['id'])
        return jsonify({
            'balance': balance,
            'balance_formatted': f'${balance:.2f}'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@credit_bp.route('/api/credit/top-up', methods=['POST'])
@require_auth
def top_up_credit():
    """Create a Stripe checkout session for topping up credit."""
    try:
        data = request.json
        amount_dollars = data.get('amount_dollars', 10.0)  # Default $10
        
        if not isinstance(amount_dollars, (int, float)) or amount_dollars < 1:
            return jsonify({'error': 'Invalid amount. Minimum is $1.00'}), 400
        
        amount_cents = int(round(amount_dollars * 100))
        
        base_url = os.getenv('BASE_URL', request.host_url.rstrip('/'))
        
        result = stripe_service.create_checkout_session(
            request.user['id'],
            amount_cents,
            f'FocalPrompt Credit Top-up: ${amount_dollars:.2f}',
            base_url
        )
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

