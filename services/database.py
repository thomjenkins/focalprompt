#!/usr/bin/env python3
"""
Database service for FocalPrompt SaaS.

Supports both SQLite (local development) and PostgreSQL (Supabase/Production).
Automatically detects DATABASE_URL environment variable to use PostgreSQL.
"""

import os
from contextlib import contextmanager
from typing import Optional, Dict, List
from datetime import datetime

# Try to import PostgreSQL driver, fall back to SQLite
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from psycopg2.pool import SimpleConnectionPool
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

import sqlite3


class Database:
    """Database service for user management, sessions, and usage tracking."""
    
    def __init__(self, db_path: str = None, database_url: str = None):
        """
        Initialize database service.
        
        Args:
            db_path: Path to SQLite database file (only used if DATABASE_URL not set)
            database_url: PostgreSQL connection string (defaults to checking env vars)
        """
        # Check for database URL in order of preference (Vercel Supabase creates multiple)
        # 1. Direct DATABASE_URL (if manually set)
        # 2. DATABASE_POSTGRES_URL (Vercel pooled connection - best for serverless)
        # 3. DATABASE_SUPABASE_URL (Vercel Supabase connection)
        # 4. DATABASE_POSTGRES_URL_NON_POOLING (direct connection, less ideal for serverless)
        self.database_url = (
            database_url or 
            os.getenv('DATABASE_URL') or
            os.getenv('DATABASE_POSTGRES_URL') or
            os.getenv('DATABASE_SUPABASE_URL') or
            os.getenv('DATABASE_POSTGRES_URL_NON_POOLING')
        )
        self.use_postgres = bool(self.database_url and POSTGRES_AVAILABLE)
        
        if self.use_postgres:
            # Use PostgreSQL (Supabase) - initialize pool lazily
            self.pool = None
            # Don't initialize pool here - do it on first use
        else:
            # Use SQLite (local development)
            if db_path is None:
                # On Vercel, use /tmp (writable directory)
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
        
        # Mark as uninitialized - will initialize on first use
        self._initialized = False
        # Don't initialize here - defer to first use to avoid import-time crashes
    
    def _clean_connection_string(self, url: str) -> str:
        """
        Clean PostgreSQL connection string by removing unsupported query parameters.
        
        Supabase and some providers add query parameters that psycopg2 doesn't recognize.
        This function removes those while keeping valid PostgreSQL parameters.
        """
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        
        try:
            # Parse the URL
            parsed = urlparse(url)
            
            # Valid PostgreSQL connection parameters (psycopg2 supports these)
            valid_params = {
                'host', 'port', 'dbname', 'user', 'password', 'sslmode', 
                'sslcert', 'sslkey', 'sslrootcert', 'sslcrl', 'connect_timeout',
                'application_name', 'options', 'keepalives', 'keepalives_idle',
                'keepalives_interval', 'keepalives_count', 'tcp_user_timeout'
            }
            
            # Parse query parameters
            query_params = parse_qs(parsed.query)
            
            # Filter out invalid parameters
            cleaned_params = {}
            for key, value in query_params.items():
                if key.lower() in valid_params:
                    cleaned_params[key] = value[0] if len(value) == 1 else value
            
            # Reconstruct URL without invalid parameters
            cleaned_query = urlencode(cleaned_params) if cleaned_params else ''
            cleaned_parsed = parsed._replace(query=cleaned_query)
            cleaned_url = urlunparse(cleaned_parsed)
            
            return cleaned_url
        except Exception as e:
            # If parsing fails, return original URL and let psycopg2 handle the error
            import sys
            print(f"Warning: Failed to clean connection string: {e}, using original", file=sys.stderr)
            return url
    
    def _init_postgres_pool(self):
        """Initialize PostgreSQL connection pool."""
        if self.pool is not None:
            return  # Already initialized
        
        try:
            # Clean connection string to remove unsupported query parameters
            cleaned_url = self._clean_connection_string(self.database_url)
            
            # Parse DATABASE_URL and create connection pool
            self.pool = SimpleConnectionPool(
                minconn=1,
                maxconn=5,
                dsn=cleaned_url
            )
        except Exception as e:
            import sys
            print(f"Warning: Failed to create PostgreSQL pool: {e}", file=sys.stderr)
            print(f"Original URL (first 50 chars): {self.database_url[:50]}...", file=sys.stderr)
            self.pool = None
            raise  # Re-raise so caller knows it failed
    
    def _ensure_initialized(self):
        """Ensure database is initialized (lazy initialization)."""
        if self._initialized:
            return  # Already initialized
        
        # Prevent recursion: if we're already initializing, don't call _init_db again
        if hasattr(self, '_initializing') and self._initializing:
            return  # Already in the process of initializing
        
        try:
            self._initializing = True  # Set flag to prevent recursion
            self._init_db()
            self._initialized = True
        except Exception as e:
            # Log but don't crash - database might not be available yet
            import sys
            print(f"Warning: Database initialization failed: {e}", file=sys.stderr)
            # Will retry on next use
            self._initialized = False
        finally:
            self._initializing = False  # Clear flag
    
    @contextmanager
    def _get_conn(self):
        """Get database connection with context manager."""
        # Ensure database is initialized before use
        self._ensure_initialized()
        
        if self.use_postgres:
            # PostgreSQL connection
            if not self.pool:
                # Try to reinitialize pool if it failed before
                try:
                    self._init_postgres_pool()
                except Exception as e:
                    raise Exception(f"PostgreSQL connection pool not available: {e}")
            
            if not self.pool:
                raise Exception("PostgreSQL connection pool not available")
            
            conn = self.pool.getconn()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                self.pool.putconn(conn)
        else:
            # SQLite connection
            try:
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
            except Exception as e:
                # If SQLite fails (e.g., on Vercel read-only filesystem), raise helpful error
                raise Exception(f"SQLite connection failed: {e}. Consider using PostgreSQL with DATABASE_URL.")
    
    def _execute(self, conn, query: str, params: tuple = None):
        """Execute query with proper cursor handling."""
        if self.use_postgres:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
        else:
            cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        return cursor
    
    def _fetchone(self, cursor):
        """Fetch one row and convert to dict."""
        row = cursor.fetchone()
        if row is None:
            return None
        
        if self.use_postgres:
            return dict(row)
        else:
            return dict(row)
    
    def _fetchall(self, cursor):
        """Fetch all rows and convert to list of dicts."""
        rows = cursor.fetchall()
        
        if self.use_postgres:
            return [dict(row) for row in rows]
        else:
            return [dict(row) for row in rows]
    
    def _init_db(self):
        """Initialize database tables."""
        try:
            # Test connection first
            with self._get_conn() as conn:
                # Get cursor for executing SQL
                if self.use_postgres:
                    cursor = conn.cursor()
                else:
                    cursor = conn
                
                # Users table
                if self.use_postgres:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id VARCHAR(255) PRIMARY KEY,
                            email VARCHAR(255) UNIQUE NOT NULL,
                            password_hash TEXT NOT NULL,
                            tier VARCHAR(50) DEFAULT 'free',
                            credit_balance REAL DEFAULT 5.0,
                            created_at TIMESTAMP NOT NULL,
                            subscription_id VARCHAR(255),
                            subscription_status VARCHAR(50) DEFAULT 'active',
                            stripe_customer_id VARCHAR(255)
                        )
                    """)
                    # Add credit_balance column if it doesn't exist (migration)
                    cursor.execute("""
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name='users' AND column_name='credit_balance'
                            ) THEN
                                ALTER TABLE users ADD COLUMN credit_balance REAL DEFAULT 5.0;
                                -- Give existing users $5 credit
                                UPDATE users SET credit_balance = 5.0 WHERE credit_balance IS NULL;
                            END IF;
                        END $$;
                    """)
                else:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id TEXT PRIMARY KEY,
                            email TEXT UNIQUE NOT NULL,
                            password_hash TEXT NOT NULL,
                            tier TEXT DEFAULT 'free',
                            credit_balance REAL DEFAULT 5.0,
                            created_at TEXT NOT NULL,
                            subscription_id TEXT,
                            subscription_status TEXT DEFAULT 'active',
                            stripe_customer_id TEXT
                        )
                    """)
                    # Add credit_balance column if it doesn't exist (migration for SQLite)
                    try:
                        cursor.execute("ALTER TABLE users ADD COLUMN credit_balance REAL DEFAULT 5.0")
                        # Give existing users $5 credit
                        cursor.execute("UPDATE users SET credit_balance = 5.0 WHERE credit_balance IS NULL")
                    except sqlite3.OperationalError:
                        # Column already exists, ignore
                        pass
                
                # Sessions table
                if self.use_postgres:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS sessions (
                            session_id VARCHAR(255) PRIMARY KEY,
                            user_id VARCHAR(255) NOT NULL,
                            expires_at TIMESTAMP NOT NULL,
                            created_at TIMESTAMP NOT NULL,
                            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                        )
                    """)
                else:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS sessions (
                            session_id TEXT PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            expires_at TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                        )
                    """)
                
                # Usage tracking table
                if self.use_postgres:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS usage (
                            id VARCHAR(255) PRIMARY KEY,
                            user_id VARCHAR(255) NOT NULL,
                            endpoint VARCHAR(255) NOT NULL,
                            tokens_used INTEGER DEFAULT 0,
                            cost REAL DEFAULT 0.0,
                            timestamp TIMESTAMP NOT NULL,
                            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                        )
                    """)
                else:
                    cursor.execute("""
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
                
                # Charges table for billing
                if self.use_postgres:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS charges (
                            id VARCHAR(255) PRIMARY KEY,
                            user_id VARCHAR(255) NOT NULL,
                            amount_cents INTEGER NOT NULL,
                            stripe_payment_intent_id VARCHAR(255),
                            description TEXT,
                            status VARCHAR(50) DEFAULT 'pending',
                            created_at TIMESTAMP NOT NULL,
                            updated_at TIMESTAMP NOT NULL,
                            metadata TEXT,
                            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                        )
                    """)
                else:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS charges (
                            id TEXT PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            amount_cents INTEGER NOT NULL,
                            stripe_payment_intent_id TEXT,
                            description TEXT,
                            status TEXT DEFAULT 'pending',
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            metadata TEXT,
                            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                        )
                    """)
                
                # Create indexes for performance
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)",
                    "CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)",
                    "CREATE INDEX IF NOT EXISTS idx_usage_user_id ON usage(user_id)",
                    "CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage(timestamp)",
                    "CREATE INDEX IF NOT EXISTS idx_usage_endpoint ON usage(endpoint)",
                    "CREATE INDEX IF NOT EXISTS idx_charges_user_id ON charges(user_id)",
                    "CREATE INDEX IF NOT EXISTS idx_charges_status ON charges(status)",
                    "CREATE INDEX IF NOT EXISTS idx_charges_created_at ON charges(created_at)"
                ]
                
                for index_sql in indexes:
                    cursor.execute(index_sql)
                
                # Close cursor for PostgreSQL
                if self.use_postgres:
                    cursor.close()
                    
        except Exception as e:
            # Log error but don't crash - database might not be available
            import sys
            print(f"Warning: Database initialization failed: {e}", file=sys.stderr)
            # Database operations will fail gracefully later
    
    # User operations
    def create_user(self, user_data: Dict) -> bool:
        """Create a new user."""
        with self._get_conn() as conn:
            try:
                if self.use_postgres:
                    cursor = self._execute(conn, """
                        INSERT INTO users (id, email, password_hash, tier, created_at, subscription_status)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        user_data['id'],
                        user_data['email'],
                        user_data['password_hash'],
                        user_data.get('tier', 'free'),
                        user_data.get('created_at', datetime.now().isoformat()),
                        user_data.get('subscription_status', 'active')
                    ))
                else:
                    cursor = self._execute(conn, """
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
                cursor.close()
                return True
            except Exception as e:
                print(f"Error creating user: {e}")
                return False
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user by ID."""
        with self._get_conn() as conn:
            if self.use_postgres:
                cursor = self._execute(conn, "SELECT * FROM users WHERE id = %s", (user_id,))
            else:
                cursor = self._execute(conn, "SELECT * FROM users WHERE id = ?", (user_id,))
            
            row = self._fetchone(cursor)
            cursor.close()
            return row
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email."""
        with self._get_conn() as conn:
            if self.use_postgres:
                cursor = self._execute(conn, "SELECT * FROM users WHERE email = %s", (email,))
            else:
                cursor = self._execute(conn, "SELECT * FROM users WHERE email = ?", (email,))
            
            row = self._fetchone(cursor)
            cursor.close()
            return row
    
    def get_user_by_subscription(self, subscription_id: str) -> Optional[Dict]:
        """Get user by Stripe subscription ID."""
        with self._get_conn() as conn:
            if self.use_postgres:
                cursor = self._execute(conn, "SELECT * FROM users WHERE subscription_id = %s", (subscription_id,))
            else:
                cursor = self._execute(conn, "SELECT * FROM users WHERE subscription_id = ?", (subscription_id,))
            
            row = self._fetchone(cursor)
            cursor.close()
            return row
    
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
                updates.append("subscription_id = %s" if self.use_postgres else "subscription_id = ?")
                params.append(subscription_id)
            
            if status:
                updates.append("subscription_status = %s" if self.use_postgres else "subscription_status = ?")
                params.append(status)
            
            if stripe_customer_id:
                updates.append("stripe_customer_id = %s" if self.use_postgres else "stripe_customer_id = ?")
                params.append(stripe_customer_id)
            
            if not updates:
                return False
            
            params.append(user_id)
            
            if self.use_postgres:
                query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
            else:
                query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            
            cursor = self._execute(conn, query, tuple(params))
            cursor.close()
            return True
    
    def update_user(self, user_id: str, updates: Dict) -> bool:
        """Update user fields."""
        with self._get_conn() as conn:
            update_parts = []
            params = []
            
            for key, value in updates.items():
                if key in ['tier', 'credit_balance', 'subscription_id', 'subscription_status', 'stripe_customer_id']:
                    update_parts.append(f"{key} = %s" if self.use_postgres else f"{key} = ?")
                    params.append(value)
            
            if not update_parts:
                return False
            
            query = f"UPDATE users SET {', '.join(update_parts)} WHERE id = %s" if self.use_postgres else f"UPDATE users SET {', '.join(update_parts)} WHERE id = ?"
            params.append(user_id)
            
            cursor = self._execute(conn, query, tuple(params))
            cursor.close()
            return True
    
    def update_user_tier(self, user_id: str, tier: str) -> bool:
        """Update user tier."""
        return self.update_user(user_id, {'tier': tier})
    
    # Session operations
    def create_session(self, session_id: str, user_id: str, expires_at: datetime) -> bool:
        """Create a new session."""
        with self._get_conn() as conn:
            try:
                created_at = datetime.now()
                
                if self.use_postgres:
                    cursor = self._execute(conn, """
                        INSERT INTO sessions (session_id, user_id, expires_at, created_at)
                        VALUES (%s, %s, %s, %s)
                    """, (session_id, user_id, expires_at, created_at))
                else:
                    cursor = self._execute(conn, """
                        INSERT INTO sessions (session_id, user_id, expires_at, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (session_id, user_id, expires_at.isoformat(), created_at.isoformat()))
                
                cursor.close()
                return True
            except Exception as e:
                print(f"Error creating session: {e}")
                return False
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session by ID."""
        with self._get_conn() as conn:
            if self.use_postgres:
                cursor = self._execute(conn, "SELECT * FROM sessions WHERE session_id = %s", (session_id,))
            else:
                cursor = self._execute(conn, "SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            
            row = self._fetchone(cursor)
            cursor.close()
            
            # Convert timestamp strings back to datetime for SQLite
            if row and not self.use_postgres:
                if 'expires_at' in row and isinstance(row['expires_at'], str):
                    row['expires_at'] = datetime.fromisoformat(row['expires_at'])
            
            return row
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        with self._get_conn() as conn:
            if self.use_postgres:
                cursor = self._execute(conn, "DELETE FROM sessions WHERE session_id = %s", (session_id,))
            else:
                cursor = self._execute(conn, "DELETE FROM sessions WHERE session_id = ?", (session_id,))
            cursor.close()
            return True
    
    def cleanup_expired_sessions(self) -> int:
        """Delete expired sessions. Returns number deleted."""
        with self._get_conn() as conn:
            now = datetime.now()
            if self.use_postgres:
                cursor = self._execute(conn, "DELETE FROM sessions WHERE expires_at < %s", (now,))
            else:
                cursor = self._execute(conn, "DELETE FROM sessions WHERE expires_at < ?", (now.isoformat(),))
            
            count = cursor.rowcount
            cursor.close()
            return count
    
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
                timestamp = datetime.now()
                
                if self.use_postgres:
                    cursor = self._execute(conn, """
                        INSERT INTO usage (id, user_id, endpoint, tokens_used, cost, timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (usage_id, user_id, endpoint, tokens_used, cost, timestamp))
                else:
                    cursor = self._execute(conn, """
                        INSERT INTO usage (id, user_id, endpoint, tokens_used, cost, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (usage_id, user_id, endpoint, tokens_used, cost, timestamp.isoformat()))
                
                cursor.close()
                return True
            except Exception as e:
                print(f"Error recording usage: {e}")
                return False
    
    def get_monthly_usage(self, user_id: str, endpoint: str) -> int:
        """Get usage count for current month for a specific endpoint."""
        with self._get_conn() as conn:
            # Get first day of current month
            now = datetime.now()
            month_start = datetime(now.year, now.month, 1)
            
            if self.use_postgres:
                cursor = self._execute(conn, """
                    SELECT COUNT(*) as count
                    FROM usage
                    WHERE user_id = %s AND endpoint = %s AND timestamp >= %s
                """, (user_id, endpoint, month_start))
            else:
                cursor = self._execute(conn, """
                    SELECT COUNT(*) as count
                    FROM usage
                    WHERE user_id = ? AND endpoint = ? AND timestamp >= ?
                """, (user_id, endpoint, month_start.isoformat()))
            
            row = self._fetchone(cursor)
            cursor.close()
            return row['count'] if row else 0
    
    def get_user_usage_summary(self, user_id: str, month: Optional[int] = None, year: Optional[int] = None) -> Dict:
        """Get usage summary for a user."""
        with self._get_conn() as conn:
            now = datetime.now()
            target_month = month or now.month
            target_year = year or now.year
            
            month_start = datetime(target_year, target_month, 1)
            if target_month == 12:
                month_end = datetime(target_year + 1, 1, 1)
            else:
                month_end = datetime(target_year, target_month + 1, 1)
            
            if self.use_postgres:
                cursor = self._execute(conn, """
                    SELECT 
                        endpoint,
                        COUNT(*) as count,
                        SUM(tokens_used) as total_tokens,
                        SUM(cost) as total_cost
                    FROM usage
                    WHERE user_id = %s AND timestamp >= %s AND timestamp < %s
                    GROUP BY endpoint
                """, (user_id, month_start, month_end))
            else:
                cursor = self._execute(conn, """
                    SELECT 
                        endpoint,
                        COUNT(*) as count,
                        SUM(tokens_used) as total_tokens,
                        SUM(cost) as total_cost
                    FROM usage
                    WHERE user_id = ? AND timestamp >= ? AND timestamp < ?
                    GROUP BY endpoint
                """, (user_id, month_start.isoformat(), month_end.isoformat()))
            
            rows = self._fetchall(cursor)
            cursor.close()
            
            summary = {}
            total_requests = 0
            total_tokens = 0
            total_cost = 0.0
            
            for row in rows:
                endpoint = row['endpoint']
                summary[endpoint] = {
                    'count': row['count'] or 0,
                    'tokens': row['total_tokens'] or 0,
                    'cost': row['total_cost'] or 0.0
                }
                total_requests += row['count'] or 0
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
