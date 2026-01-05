#!/usr/bin/env python3
"""
Stripe payment service for FocalPrompt SaaS.

Handles subscription management, checkout sessions, and webhooks.
"""

import stripe
import os
from typing import Dict, Optional
from services.database import Database


class StripeService:
    """Service for Stripe payment processing."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Stripe service.
        
        Args:
            api_key: Stripe API key (defaults to env var)
        """
        self.api_key = api_key or os.getenv('STRIPE_SECRET_KEY')
        if self.api_key:
            stripe.api_key = self.api_key
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        self.db = Database()
    
    def create_checkout_session(
        self,
        user_id: str,
        tier: str,
        base_url: str
    ) -> Dict:
        """
        Create Stripe checkout session for subscription.
        
        Args:
            user_id: User ID
            tier: Subscription tier ('starter', 'professional', 'enterprise')
            base_url: Base URL for redirects
            
        Returns:
            Dict with checkout_url or error
        """
        if not self.api_key:
            return {'error': 'Stripe not configured'}
        
        # Get user
        user = self.db.get_user_by_id(user_id)
        if not user:
            return {'error': 'User not found'}
        
        # Price IDs - these need to be created in Stripe dashboard
        # For now, using placeholder structure
        price_ids = {
            'starter': os.getenv('STRIPE_PRICE_STARTER', 'price_starter'),
            'professional': os.getenv('STRIPE_PRICE_PROFESSIONAL', 'price_professional'),
            'enterprise': os.getenv('STRIPE_PRICE_ENTERPRISE', 'price_enterprise')
        }
        
        price_id = price_ids.get(tier)
        if not price_id:
            return {'error': f'Invalid tier: {tier}'}
        
        try:
            # Create or get Stripe customer
            customer_id = user.get('stripe_customer_id')
            if not customer_id:
                customer = stripe.Customer.create(
                    email=user['email'],
                    metadata={'user_id': user_id}
                )
                customer_id = customer.id
                self.db.update_user_subscription(
                    user_id,
                    None,
                    'active',
                    customer_id
                )
            
            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=f'{base_url}/dashboard?success=true',
                cancel_url=f'{base_url}/dashboard?canceled=true',
                metadata={
                    'user_id': user_id,
                    'tier': tier
                }
            )
            
            return {
                'checkout_url': session.url,
                'session_id': session.id
            }
            
        except stripe.error.StripeError as e:
            return {'error': f'Stripe error: {str(e)}'}
        except Exception as e:
            return {'error': f'Error creating checkout: {str(e)}'}
    
    def create_portal_session(self, user_id: str, base_url: str) -> Dict:
        """
        Create Stripe customer portal session.
        
        Args:
            user_id: User ID
            base_url: Base URL for redirect
            
        Returns:
            Dict with portal_url or error
        """
        if not self.api_key:
            return {'error': 'Stripe not configured'}
        
        user = self.db.get_user_by_id(user_id)
        if not user:
            return {'error': 'User not found'}
        
        customer_id = user.get('stripe_customer_id')
        if not customer_id:
            return {'error': 'No active subscription'}
        
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=f'{base_url}/dashboard'
            )
            
            return {'portal_url': session.url}
            
        except stripe.error.StripeError as e:
            return {'error': f'Stripe error: {str(e)}'}
    
    def handle_webhook(self, payload: bytes, signature: str) -> Dict:
        """
        Handle Stripe webhook events.
        
        Args:
            payload: Webhook payload bytes
            signature: Stripe signature header
            
        Returns:
            Dict with status
        """
        if not self.webhook_secret:
            return {'error': 'Webhook secret not configured'}
        
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                self.webhook_secret
            )
        except ValueError as e:
            return {'error': f'Invalid payload: {str(e)}'}
        except stripe.error.SignatureVerificationError as e:
            return {'error': f'Invalid signature: {str(e)}'}
        
        # Handle different event types
        event_type = event['type']
        event_data = event['data']['object']
        
        if event_type == 'checkout.session.completed':
            # Subscription created
            session = event_data
            user_id = session['metadata'].get('user_id')
            subscription_id = session.get('subscription')
            tier = session['metadata'].get('tier', 'starter')
            
            if user_id and subscription_id:
                self.db.update_user_subscription(
                    user_id,
                    subscription_id,
                    'active'
                )
                self.db.update_user_tier(user_id, tier)
        
        elif event_type == 'customer.subscription.updated':
            # Subscription updated
            subscription = event_data
            user = self.db.get_user_by_subscription(subscription['id'])
            
            if user:
                status = subscription['status']
                if status in ['active', 'trialing']:
                    self.db.update_user_subscription(
                        user['id'],
                        subscription['id'],
                        'active'
                    )
                else:
                    self.db.update_user_subscription(
                        user['id'],
                        subscription['id'],
                        status
                    )
        
        elif event_type == 'customer.subscription.deleted':
            # Subscription canceled
            subscription = event_data
            user = self.db.get_user_by_subscription(subscription['id'])
            
            if user:
                self.db.update_user_subscription(
                    user['id'],
                    None,
                    'canceled'
                )
                # Downgrade to free tier
                self.db.update_user_tier(user['id'], 'free')
        
        return {'status': 'success', 'event_type': event_type}

