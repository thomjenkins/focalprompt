#!/usr/bin/env python3
"""
Vercel serverless function entry point.

This is the entry point for Vercel's serverless functions.
"""

from app_new import app

# Export the app for Vercel
handler = app

