#!/usr/bin/env python3
"""
Billing service for pay-as-you-go pricing.

Handles cost calculation with markup, Stripe payment processing,
and usage tracking for billing.
"""

import os
from typing import Dict, Optional, Tuple
from decimal import Decimal, ROUND_UP
from services.cost_calculator import CostCalculator
from services.database import Database
from services.stripe_service import StripeService


class BillingService:
    """Service for handling pay-as-you-go billing with markup."""
    
    # Markup percentage (50% = 1.5x multiplier)
    MARKUP_MULTIPLIER = 1.5
    
    # Minimum charge amount (in cents) - avoid micro-transactions
    MIN_CHARGE_CENTS = 50  # $0.50 minimum
    
    def __init__(self, db: Database = None, stripe_service: StripeService = None):
        """
        Initialize billing service.
        
        Args:
            db: Database instance
            stripe_service: Stripe service instance
        """
        self.db = db or Database()
        self.stripe_service = stripe_service or StripeService()
        self.cost_calculator = CostCalculator()
    
    def calculate_charge_amount(
        self,
        input_tokens: int,
        output_tokens: int,
        embedding_tokens: int,
        model: str,
        provider: str = 'openai'
    ) -> Dict[str, float]:
        """
        Calculate charge amount with 50% markup.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            embedding_tokens: Number of embedding tokens
            model: Model name
            provider: Provider name
            
        Returns:
            Dict with:
            - base_cost: Cost from provider (Vercel's cost)
            - markup: Markup amount (50% of base)
            - total_cost: Total cost to charge user
            - total_cents: Total in cents (for Stripe)
        """
        # Calculate base cost (what Vercel charges us)
        cost_breakdown = self.cost_calculator.calculate_cost(
            input_tokens,
            output_tokens,
            embedding_tokens,
            model,
            provider
        )
        
        base_cost = cost_breakdown.get('total_cost', 0.0)
        
        # Calculate markup (50% = multiply by 1.5)
        total_cost = base_cost * self.MARKUP_MULTIPLIER
        markup = total_cost - base_cost
        
        # Convert to cents for Stripe
        total_cents = int(round(total_cost * 100))
        
        # Apply minimum charge
        if total_cents > 0 and total_cents < self.MIN_CHARGE_CENTS:
            total_cents = self.MIN_CHARGE_CENTS
            total_cost = total_cents / 100.0
            markup = total_cost - base_cost
        
        return {
            'base_cost': base_cost,
            'markup': markup,
            'total_cost': total_cost,
            'total_cents': total_cents,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'embedding_tokens': embedding_tokens,
            'model': model,
            'provider': provider
        }
    
    def charge_user(
        self,
        user_id: str,
        amount_cents: int,
        description: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Charge a user via Stripe payment intent.
        
        Args:
            user_id: User ID
            amount_cents: Amount in cents
            description: Description for the charge
            metadata: Optional metadata for the charge
            
        Returns:
            Dict with charge result or error
        """
        if amount_cents < self.MIN_CHARGE_CENTS:
            return {
                'error': f'Amount too small. Minimum charge is ${self.MIN_CHARGE_CENTS / 100:.2f}'
            }
        
        # Get user
        user = self.db.get_user_by_id(user_id)
        if not user:
            return {'error': 'User not found'}
        
        # Get or create Stripe customer
        stripe_customer_id = user.get('stripe_customer_id')
        if not stripe_customer_id:
            # Create Stripe customer
            result = self.stripe_service.create_customer(user_id, user['email'])
            if 'error' in result:
                return result
            stripe_customer_id = result['customer_id']
        
        # Create payment intent
        try:
            import stripe
            stripe.api_key = self.stripe_service.api_key
            
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency='usd',
                customer=stripe_customer_id,
                description=description,
                metadata={
                    'user_id': user_id,
                    **(metadata or {})
                },
                automatic_payment_methods={
                    'enabled': True
                }
            )
            
            # Record the charge in database
            self.db.record_charge(
                user_id=user_id,
                amount_cents=amount_cents,
                stripe_payment_intent_id=payment_intent.id,
                description=description,
                status='pending'
            )
            
            return {
                'success': True,
                'payment_intent_id': payment_intent.id,
                'client_secret': payment_intent.client_secret,
                'amount_cents': amount_cents,
                'amount_dollars': amount_cents / 100.0
            }
            
        except Exception as e:
            return {'error': f'Failed to create payment intent: {str(e)}'}
    
    def get_user_balance(self, user_id: str) -> Dict:
        """
        Get user's billing balance (pending charges, total spent, etc.).
        
        Args:
            user_id: User ID
            
        Returns:
            Dict with balance information
        """
        charges = self.db.get_user_charges(user_id)
        
        total_spent = sum(c.get('amount_cents', 0) for c in charges if c.get('status') == 'succeeded')
        pending_charges = sum(c.get('amount_cents', 0) for c in charges if c.get('status') == 'pending')
        
        return {
            'total_spent_cents': total_spent,
            'total_spent_dollars': total_spent / 100.0,
            'pending_charges_cents': pending_charges,
            'pending_charges_dollars': pending_charges / 100.0,
            'total_charges': len(charges),
            'successful_charges': len([c for c in charges if c.get('status') == 'succeeded'])
        }
    
    def process_usage_charge(
        self,
        user_id: str,
        input_tokens: int,
        output_tokens: int,
        embedding_tokens: int,
        model: str,
        provider: str,
        endpoint: str
    ) -> Dict:
        """
        Process a usage charge for an API call.
        
        This calculates the cost with markup and creates a payment intent.
        
        Args:
            user_id: User ID
            input_tokens: Input tokens used
            output_tokens: Output tokens used
            embedding_tokens: Embedding tokens used
            model: Model used
            provider: Provider used
            endpoint: API endpoint called
            
        Returns:
            Dict with charge information or error
        """
        # Calculate charge amount
        charge_info = self.calculate_charge_amount(
            input_tokens,
            output_tokens,
            embedding_tokens,
            model,
            provider
        )
        
        # Create description
        description = f"FocalPrompt API usage: {endpoint} ({model})"
        
        # Create metadata
        metadata = {
            'endpoint': endpoint,
            'model': model,
            'provider': provider,
            'input_tokens': str(input_tokens),
            'output_tokens': str(output_tokens),
            'embedding_tokens': str(embedding_tokens),
            'base_cost': f"{charge_info['base_cost']:.6f}",
            'markup': f"{charge_info['markup']:.6f}"
        }
        
        # Charge user
        result = self.charge_user(
            user_id=user_id,
            amount_cents=charge_info['total_cents'],
            description=description,
            metadata=metadata
        )
        
        if 'error' in result:
            return result
        
        # Add charge info to result
        result['charge_info'] = charge_info
        
        return result

