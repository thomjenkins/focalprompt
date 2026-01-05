# FocalPrompt SaaS Setup Guide

## ✅ Implementation Complete!

All core SaaS features have been implemented:

### What's Been Built

1. **Database Service** (`services/database.py`)
   - SQLite database with users, sessions, and usage tables
   - Can be migrated to PostgreSQL later

2. **Authentication Service** (`services/auth_service.py`)
   - User registration and login
   - Password hashing with Werkzeug
   - Session management

3. **Usage Tracking** (`services/usage_service.py`)
   - Tier-based limits
   - Monthly usage tracking
   - Quota checking

4. **Stripe Integration** (`services/stripe_service.py`)
   - Checkout session creation
   - Customer portal
   - Webhook handling

5. **Routes**
   - `/api/auth/register` - User registration
   - `/api/auth/login` - User login
   - `/api/auth/logout` - User logout
   - `/api/auth/me` - Get current user
   - `/api/payment/create-checkout` - Create Stripe checkout
   - `/api/payment/portal` - Customer portal
   - `/api/payment/webhook` - Stripe webhooks
   - `/api/usage/summary` - Usage summary
   - `/api/usage/quota` - Check quota

6. **Frontend**
   - Login page (`/login`)
   - Signup page (`/signup`)
   - Auth UI in main page header
   - Session management in JavaScript

## Setup Instructions

### 1. Install Dependencies

```bash
cd /Users/thomasjenkins/FocalPrompt
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create a `.env` file or set environment variables:

```bash
# Required
SECRET_KEY=your-secret-key-here-change-in-production

# Optional (for Stripe)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_STARTER=price_...
STRIPE_PRICE_PROFESSIONAL=price_...
STRIPE_PRICE_ENTERPRISE=price_...

# Optional
BASE_URL=http://localhost:5001
```

### 3. Initialize Database

The database will be created automatically on first run at `data/focalprompt.db`.

### 4. Run the Application

```bash
python3 app_new.py
```

## Stripe Setup

### 1. Create Stripe Account

1. Go to https://stripe.com
2. Create account (use test mode for development)
3. Get API keys from Dashboard → Developers → API keys

### 2. Create Products and Prices

1. Go to Products in Stripe Dashboard
2. Create products:
   - **Starter** - $29/month
   - **Professional** - $99/month
   - **Enterprise** - $499/month
3. Copy the Price IDs (starts with `price_`)
4. Add them to environment variables

### 3. Set Up Webhooks

1. Go to Developers → Webhooks
2. Add endpoint: `https://yourdomain.com/api/payment/webhook`
3. Select events:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. Copy webhook signing secret (starts with `whsec_`)
5. Add to environment variables

## Usage

### For Users

1. **Sign Up**: Go to `/signup` and create an account
2. **Login**: Go to `/login` and sign in
3. **Use Service**: All features work with usage tracking
4. **Upgrade**: Use payment endpoints to upgrade tier

### For Developers

#### Register a User

```bash
curl -X POST http://localhost:5001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'
```

#### Login

```bash
curl -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'
```

Response includes `session_id` - use this in `X-Session-ID` header for authenticated requests.

#### Check Usage

```bash
curl -X GET http://localhost:5001/api/usage/summary \
  -H "X-Session-ID: your-session-id"
```

## Tier Limits

| Tier | Assessments/Month | Ablation/Month | Batch/Month | Agent Builds/Month |
|------|-------------------|----------------|-------------|-------------------|
| Free | 10 | 2 | 1 | 5 |
| Starter | 100 | 20 | 10 | 50 |
| Professional | 1,000 | 200 | 100 | 500 |
| Enterprise | Unlimited | Unlimited | Unlimited | Unlimited |

## Next Steps

1. **Set up Stripe** (see above)
2. **Test authentication flow**
3. **Test usage tracking**
4. **Deploy to production**
5. **Set up monitoring**
6. **Add user dashboard** (optional)

## Notes

- Authentication is **optional** for now - routes work with or without login
- Usage limits only apply to authenticated users
- Database is SQLite - migrate to PostgreSQL for production
- Stripe is optional - app works without it (users stay on free tier)

## Troubleshooting

### Database errors
- Make sure `data/` directory is writable
- Check database file permissions

### Authentication not working
- Check `SECRET_KEY` is set
- Verify session ID is being sent in headers
- Check browser console for errors

### Stripe errors
- Verify API keys are correct
- Check webhook endpoint is accessible
- Use Stripe test mode for development

