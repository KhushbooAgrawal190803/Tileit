"""
Authentication system for roofing companies
Handles user registration, login, and session management
"""

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
    """Manages user authentication and sessions"""
    
    def __init__(self):
        self.users = {}  # In production, use a database
        self.sessions = {}  # Session storage
        self.load_users()
    
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
        if email in [user.email for user in self.users.values()]:
            return None  # Email already exists
        
        user_id = secrets.token_urlsafe(16)
        now = datetime.now().isoformat()
        
        user = User(
            id=user_id,
            email=email,
            password_hash=hashlib.sha256(password.encode()).hexdigest(),  # Simple hash for demo
            business_name=business_name,
            license_id=license_id,
            primary_zip_code=primary_zip_code,
            created_at=now,
            last_login=now
        )
        
        self.users[user_id] = user
        self.save_users()
        return user
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user login"""
        for user in self.users.values():
            if user.email == email and self.verify_password(password, user.password_hash):
                user.last_login = datetime.now().isoformat()
                self.save_users()
                return user
        return None
    
    def create_session(self, user: User) -> str:
        """Create user session"""
        token = self.generate_session_token()
        self.sessions[token] = {
            'user_id': user.id,
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(hours=24)).isoformat()
        }
        return token
    
    def get_user_from_session(self, token: str) -> Optional[User]:
        """Get user from session token"""
        if token not in self.sessions:
            return None
        
        session = self.sessions[token]
        if datetime.now().isoformat() > session['expires_at']:
            del self.sessions[token]
            return None
        
        user_id = session['user_id']
        return self.users.get(user_id)
    
    def logout(self, token: str):
        """Logout user and remove session"""
        if token in self.sessions:
            del self.sessions[token]
    
    def save_users(self):
        """Save users to file (in production, use database)"""
        try:
            with open('users.json', 'w') as f:
                users_data = {uid: user.to_dict() for uid, user in self.users.items()}
                json.dump(users_data, f, indent=2)
        except Exception as e:
            print(f"Error saving users: {e}")
    
    def load_users(self):
        """Load users from file (in production, use database)"""
        try:
            with open('users.json', 'r') as f:
                users_data = json.load(f)
                for uid, user_data in users_data.items():
                    self.users[uid] = User(**user_data)
        except FileNotFoundError:
            pass  # No users file yet
        except Exception as e:
            print(f"Error loading users: {e}")

# Global auth manager instance
auth_manager = AuthManager()
