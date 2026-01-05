#!/usr/bin/env python3
"""
Database service for FocalPrompt SaaS.

Handles all database operations using SQLite (can be migrated to PostgreSQL later).
"""

import sqlite3
import os
from contextlib import contextmanager
from typing import Optional, Dict, List
from datetime import datetime


class Database:
    """Database service for user management, sessions, and usage tracking."""
    
    def __init__(self, db_path: str = None):
        """
        Initialize database service.
        
        Args:
            db_path: Path to SQLite database file (defaults to data/focalprompt.db or /tmp on Vercel)
        """
        if db_path is None:
            # On Vercel, use /tmp (writable directory)
            # In production, should use PostgreSQL via DATABASE_URL
            if os.getenv('VERCEL') or os.path.exists('/tmp'):
                db_path = "/tmp/focalprompt.db"
            else:
                db_path = "data/focalprompt.db"
        
        self.db_path = db_path
        
        # Try to create directory, but don't fail if we can't (e.g., on Vercel)
        try:
            dir_path = os.path.dirname(db_path)
            if dir_path and dir_path != '/tmp':
                os.makedirs(dir_path, exist_ok=True)
        except (OSError, PermissionError):
            # If we can't create directory, try /tmp as fallback
            if not db_path.startswith('/tmp'):
                self.db_path = "/tmp/focalprompt.db"
        
        self._init_db()
    
    @contextmanager
    def _get_conn(self):
        """Get database connection with context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dict-like objects
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        """Initialize database tables."""
        try:
            with self._get_conn() as conn:
                # Users table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        tier TEXT DEFAULT 'free',
                        created_at TEXT NOT NULL,
                        subscription_id TEXT,
                        subscription_status TEXT DEFAULT 'active',
                        stripe_customer_id TEXT
                    )
                """)
                
                # Sessions table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                
                # Usage tracking table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS usage (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        endpoint TEXT NOT NULL,
                        tokens_used INTEGER DEFAULT 0,
                        cost REAL DEFAULT 0.0,
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                
                # Create indexes for performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_user_id ON usage(user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage(timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_endpoint ON usage(endpoint)")
        except Exception as e:
            # Log error but don't crash - database might not be available on Vercel
            # In production, should use PostgreSQL
            import sys
            print(f"Warning: Database initialization failed: {e}", file=sys.stderr)
            # Database operations will fail gracefully later
        except Exception as e:
            # Log error but don't crash - database might not be available on Vercel
            # In production, should use PostgreSQL
            import sys
            print(f"Warning: Database initialization failed: {e}", file=sys.stderr)
            # Database operations will fail gracefully later
    
    # User operations
    def create_user(self, user_data: Dict) -> bool:
        """Create a new user."""
        with self._get_conn() as conn:
            try:
                conn.execute("""
                    INSERT INTO users (id, email, password_hash, tier, created_at, subscription_status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    user_data['id'],
                    user_data['email'],
                    user_data['password_hash'],
                    user_data.get('tier', 'free'),
                    user_data.get('created_at', datetime.now().isoformat()),
                    user_data.get('subscription_status', 'active')
                ))
                return True
            except sqlite3.IntegrityError:
                return False
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user by ID."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()
            return dict(row) if row else None
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,)
            ).fetchone()
            return dict(row) if row else None
    
    def get_user_by_subscription(self, subscription_id: str) -> Optional[Dict]:
        """Get user by Stripe subscription ID."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE subscription_id = ?",
                (subscription_id,)
            ).fetchone()
            return dict(row) if row else None
    
    def update_user_subscription(
        self,
        user_id: str,
        subscription_id: Optional[str],
        status: str,
        stripe_customer_id: Optional[str] = None
    ) -> bool:
        """Update user subscription."""
        with self._get_conn() as conn:
            updates = []
            params = []
            
            if subscription_id is not None:
                updates.append("subscription_id = ?")
                params.append(subscription_id)
            
            if status:
                updates.append("subscription_status = ?")
                params.append(status)
            
            if stripe_customer_id:
                updates.append("stripe_customer_id = ?")
                params.append(stripe_customer_id)
            
            if not updates:
                return False
            
            params.append(user_id)
            conn.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
                params
            )
            return True
    
    def update_user_tier(self, user_id: str, tier: str) -> bool:
        """Update user tier."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET tier = ? WHERE id = ?",
                (tier, user_id)
            )
            return True
    
    # Session operations
    def create_session(self, session_id: str, user_id: str, expires_at: datetime) -> bool:
        """Create a new session."""
        with self._get_conn() as conn:
            try:
                conn.execute("""
                    INSERT INTO sessions (session_id, user_id, expires_at, created_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    session_id,
                    user_id,
                    expires_at.isoformat(),
                    datetime.now().isoformat()
                ))
                return True
            except sqlite3.IntegrityError:
                return False
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session by ID."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            return dict(row) if row else None
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            return True
    
    def cleanup_expired_sessions(self) -> int:
        """Delete expired sessions. Returns number deleted."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE expires_at < ?",
                (datetime.now().isoformat(),)
            )
            return cursor.rowcount
    
    # Usage operations
    def record_usage(
        self,
        usage_id: str,
        user_id: str,
        endpoint: str,
        tokens_used: int = 0,
        cost: float = 0.0
    ) -> bool:
        """Record API usage."""
        with self._get_conn() as conn:
            try:
                conn.execute("""
                    INSERT INTO usage (id, user_id, endpoint, tokens_used, cost, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    usage_id,
                    user_id,
                    endpoint,
                    tokens_used,
                    cost,
                    datetime.now().isoformat()
                ))
                return True
            except sqlite3.IntegrityError:
                return False
    
    def get_monthly_usage(self, user_id: str, endpoint: str) -> int:
        """Get usage count for current month for a specific endpoint."""
        with self._get_conn() as conn:
            # Get first day of current month
            now = datetime.now()
            month_start = datetime(now.year, now.month, 1).isoformat()
            
            row = conn.execute("""
                SELECT COUNT(*) as count
                FROM usage
                WHERE user_id = ? AND endpoint = ? AND timestamp >= ?
            """, (user_id, endpoint, month_start)).fetchone()
            
            return row['count'] if row else 0
    
    def get_user_usage_summary(self, user_id: str, month: Optional[int] = None, year: Optional[int] = None) -> Dict:
        """Get usage summary for a user."""
        with self._get_conn() as conn:
            now = datetime.now()
            target_month = month or now.month
            target_year = year or now.year
            
            month_start = datetime(target_year, target_month, 1).isoformat()
            if target_month == 12:
                month_end = datetime(target_year + 1, 1, 1).isoformat()
            else:
                month_end = datetime(target_year, target_month + 1, 1).isoformat()
            
            rows = conn.execute("""
                SELECT 
                    endpoint,
                    COUNT(*) as count,
                    SUM(tokens_used) as total_tokens,
                    SUM(cost) as total_cost
                FROM usage
                WHERE user_id = ? AND timestamp >= ? AND timestamp < ?
                GROUP BY endpoint
            """, (user_id, month_start, month_end)).fetchall()
            
            summary = {}
            total_requests = 0
            total_tokens = 0
            total_cost = 0.0
            
            for row in rows:
                endpoint = row['endpoint']
                summary[endpoint] = {
                    'count': row['count'],
                    'tokens': row['total_tokens'] or 0,
                    'cost': row['total_cost'] or 0.0
                }
                total_requests += row['count']
                total_tokens += row['total_tokens'] or 0
                total_cost += row['total_cost'] or 0.0
            
            return {
                'by_endpoint': summary,
                'total_requests': total_requests,
                'total_tokens': total_tokens,
                'total_cost': total_cost,
                'month': target_month,
                'year': target_year
            }

