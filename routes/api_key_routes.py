#!/usr/bin/env python3
"""Manage API keys (create with session; list/revoke with session or API key)."""

from datetime import datetime

from flask import Blueprint, request, jsonify

from middleware.auth import require_auth, require_session_auth
from services.api_key_service import ApiKeyService
from services.database import Database

api_key_bp = Blueprint('api_keys', __name__)
_db = None


def _get_api_key_service() -> ApiKeyService:
    global _db
    if _db is None:
        _db = Database()
    return ApiKeyService(_db)


def _dt_json(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return v


@api_key_bp.route('/api/v1/keys', methods=['GET'])
@require_auth
def list_api_keys():
    try:
        rows = _get_api_key_service().list_keys(request.user['id'])
        out = []
        for r in rows:
            rev = r.get('revoked_at')
            out.append({
                'id': r['id'],
                'key_prefix': r['key_prefix'],
                'name': r.get('name'),
                'created_at': _dt_json(r.get('created_at')),
                'last_used_at': _dt_json(r.get('last_used_at')),
                'revoked': rev is not None and (not isinstance(rev, str) or len(str(rev).strip()) > 0),
            })
        return jsonify({'keys': out})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_key_bp.route('/api/v1/keys', methods=['POST'])
@require_session_auth
def create_api_key():
    try:
        data = request.json or {}
        name = data.get('name') or None
        created = _get_api_key_service().create_key(request.user['id'], name=name)
        if not created:
            return jsonify({'error': 'Failed to create API key'}), 500
        return jsonify({
            'id': created['id'],
            'key': created['key'],
            'key_prefix': created['key_prefix'],
            'name': created['name'],
            'message': 'Store the key securely; it will not be shown again.',
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_key_bp.route('/api/v1/keys/<key_id>', methods=['DELETE'])
@require_auth
def revoke_api_key(key_id: str):
    try:
        ok = _get_api_key_service().revoke(key_id, request.user['id'])
        if not ok:
            return jsonify({'error': 'Key not found or already revoked'}), 404
        return jsonify({'success': True, 'id': key_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
