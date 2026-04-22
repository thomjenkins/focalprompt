#!/usr/bin/env python3
"""Create and verify API keys for product / server-to-server integration."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from typing import Any, Dict, List, Optional, Tuple

from services.database import Database

KEY_PREFIX = "fp_live_"


def _hash_secret(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ApiKeyService:
    """Issue keys (show once) and verify Bearer tokens."""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _prefix_for_display(secret: str) -> str:
        if len(secret) <= 20:
            return secret
        return secret[:18] + "…"

    def create_key(self, user_id: str, name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Create a key. Returns a dict with the full secret in `key` (shown only once) or None on failure.
        """
        key_id = str(uuid.uuid4())
        tail = secrets.token_urlsafe(32)
        secret = f"{KEY_PREFIX}{tail}"
        key_hash = _hash_secret(secret)
        key_prefix = self._prefix_for_display(secret)
        if not self.db.insert_api_key(key_id, user_id, key_hash, key_prefix, name):
            return None
        return {
            "id": key_id,
            "key": secret,
            "key_prefix": key_prefix,
            "name": name,
        }

    def get_user_for_bearer(
        self, auth_header: str
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        If auth_header is a valid API key, return (user_dict, key_id) matching session user shape.
        """
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return None, None
        token = auth_header[7:].strip()
        if not token.startswith(KEY_PREFIX) or len(token) < len(KEY_PREFIX) + 8:
            return None, None
        key_hash = _hash_secret(token)
        row = self.db.get_api_key_by_hash(key_hash)
        if not row:
            return None, None
        self.db.touch_api_key_last_used(row["id"])
        u = self.db.get_user_by_id(row["user_id"])
        if not u or u.get("subscription_status") != "active":
            return None, None
        return (
            {
                "id": u["id"],
                "email": u["email"],
                "tier": u.get("tier", "free"),
                "subscription_status": u.get("subscription_status", "active"),
            },
            row["id"],
        )

    def list_keys(self, user_id: str) -> List[Dict[str, Any]]:
        return self.db.list_api_keys(user_id)

    def revoke(self, key_id: str, user_id: str) -> bool:
        return self.db.revoke_api_key(key_id, user_id)
