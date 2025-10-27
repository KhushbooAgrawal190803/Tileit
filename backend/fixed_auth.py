"""
Fixed Authentication system for roofing companies
Proper user management with SQLite database
"""

import sqlite3
import hashlib
import secrets
import json
from datetime import datetime, timedelta
from typing import Optional, Dict
from dataclasses import dataclass, asdict

@dataclass
class User:
    """User account for roofing company"""
    id: str
    email: str
    password_hash: str
    business_name: str
    license_id: str
    primary_zip_code: str
    created_at: str
    last_login: str
    is_active: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "email": self.email,
            "business_name": self.business_name,
            "license_id": self.license_id,
            "primary_zip_code": self.primary_zip_code,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "is_active": self.is_active
        }

class AuthManager:
    """Manages user authentication with SQLite database"""
    
    def __init__(self):
        self.db_path = "roofing_users.db"
        self.sessions = {}  # Session storage
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                business_name TEXT NOT NULL,
                license_id TEXT NOT NULL,
                primary_zip_code TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Create sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def hash_password(self, password: str) -> str:
        """Hash password with salt"""
        salt = secrets.token_hex(16)
        return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
    
    def verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify password against stored hash"""
        # For simplicity, we'll use a basic hash comparison
        # In production, use proper password hashing
        return hashlib.sha256(password.encode()).hexdigest() == stored_hash
    
    def generate_session_token(self) -> str:
        """Generate secure session token"""
        return secrets.token_urlsafe(32)
    
    def create_user(self, email: str, password: str, business_name: str, 
                   license_id: str, primary_zip_code: str) -> Optional[User]:
        """Create new user account"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check if email already exists
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                return None  # Email already exists
            
            user_id = secrets.token_urlsafe(16)
            now = datetime.now().isoformat()
            
            # Hash password
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            # Insert user
            cursor.execute('''
                INSERT INTO users (id, email, password_hash, business_name, license_id, primary_zip_code, created_at, last_login)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, email, password_hash, business_name, license_id, primary_zip_code, now, now))
            
            conn.commit()
            
            user = User(
                id=user_id,
                email=email,
                password_hash=password_hash,
                business_name=business_name,
                license_id=license_id,
                primary_zip_code=primary_zip_code,
                created_at=now,
                last_login=now
            )
            
            return user
            
        except Exception as e:
            print(f"Error creating user: {e}")
            return None
        finally:
            conn.close()
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user login"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT id, email, password_hash, business_name, license_id, primary_zip_code, created_at, last_login, is_active
                FROM users WHERE email = ? AND is_active = 1
            ''', (email,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            user_id, email, password_hash, business_name, license_id, primary_zip_code, created_at, last_login, is_active = row
            
            if self.verify_password(password, password_hash):
                # Update last login
                now = datetime.now().isoformat()
                cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, user_id))
                conn.commit()
                
                user = User(
                    id=user_id,
                    email=email,
                    password_hash=password_hash,
                    business_name=business_name,
                    license_id=license_id,
                    primary_zip_code=primary_zip_code,
                    created_at=created_at,
                    last_login=now,
                    is_active=bool(is_active)
                )
                
                return user
            
            return None
            
        except Exception as e:
            print(f"Error authenticating user: {e}")
            return None
        finally:
            conn.close()
    
    def create_session(self, user: User) -> str:
        """Create user session"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            token = self.generate_session_token()
            now = datetime.now().isoformat()
            expires_at = (datetime.now() + timedelta(hours=24)).isoformat()
            
            # Store session in database
            cursor.execute('''
                INSERT OR REPLACE INTO sessions (token, user_id, created_at, expires_at)
                VALUES (?, ?, ?, ?)
            ''', (token, user.id, now, expires_at))
            
            conn.commit()
            return token
            
        except Exception as e:
            print(f"Error creating session: {e}")
            return None
        finally:
            conn.close()
    
    def get_user_from_session(self, token: str) -> Optional[User]:
        """Get user from session token"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check session validity
            cursor.execute('''
                SELECT s.user_id, s.expires_at, u.id, u.email, u.password_hash, u.business_name, 
                       u.license_id, u.primary_zip_code, u.created_at, u.last_login, u.is_active
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = ? AND s.expires_at > ? AND u.is_active = 1
            ''', (token, datetime.now().isoformat()))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            user_id, expires_at, id, email, password_hash, business_name, license_id, primary_zip_code, created_at, last_login, is_active = row
            
            user = User(
                id=id,
                email=email,
                password_hash=password_hash,
                business_name=business_name,
                license_id=license_id,
                primary_zip_code=primary_zip_code,
                created_at=created_at,
                last_login=last_login,
                is_active=bool(is_active)
            )
            
            return user
            
        except Exception as e:
            print(f"Error getting user from session: {e}")
            return None
        finally:
            conn.close()
    
    def logout(self, token: str):
        """Logout user and remove session"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
        except Exception as e:
            print(f"Error logging out: {e}")
        finally:
            conn.close()

# Global auth manager instance
auth_manager = AuthManager()
