import json
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, session, redirect, url_for, render_template
import jwt

class AuthManager:
    def __init__(self, credentials_file='credentials.json', secret_key=None):
        self.credentials_file = credentials_file
        self.secret_key = secret_key or secrets.token_hex(32)
        self.credentials = self.load_credentials()
    
    def load_credentials(self):
        """Load credentials from JSON file"""
        try:
            with open(self.credentials_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Create initial structure if file doesn't exist
            initial_data = {
                "users": [],
                "sessions": {},
                "_current_user_id": 1000
            }
            self.save_credentials(initial_data)
            return initial_data
        except json.JSONDecodeError:
            print(f"Error decoding JSON from {self.credentials_file}. Creating new file.")
            initial_data = {
                "users": [],
                "sessions": {},
                "_current_user_id": 1000
            }
            self.save_credentials(initial_data)
            return initial_data
    
    def save_credentials(self, data=None):
        """Save credentials to JSON file"""
        if data is None:
            data = self.credentials
        try:
            with open(self.credentials_file, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving credentials: {e}")
    
    def get_next_user_id(self):
        """Get next user ID"""
        current_id = self.credentials.get('_current_user_id', 1000)
        self.credentials['_current_user_id'] = current_id + 1
        return current_id + 1
    
    def hash_password(self, password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password, hashed_password):
        """Verify password against hash"""
        return self.hash_password(password) == hashed_password
    
    def find_user_by_email(self, email):
        """Find user by email"""
        for user in self.credentials['users']:
            if user['email'].lower() == email.lower():
                return user
        return None
    
    def create_user(self, name, email, password, auth_type='email'):
        """Create a new user"""
        # Check if user already exists
        existing_user = self.find_user_by_email(email)
        if existing_user:
            return None, "User with this email already exists"
        
        # Validate password length
        if auth_type == 'email' and len(password) < 6:
            return None, "Password must be at least 6 characters long"
        
        # Create new user
        new_user = {
            'id': self.get_next_user_id(),
            'name': name,
            'email': email.lower(),
            'password': self.hash_password(password) if auth_type == 'email' else None,
            'auth_type': auth_type,
            'created_at': datetime.now().isoformat(),
            'last_login': None,
            'is_active': True
        }
        
        self.credentials['users'].append(new_user)
        self.save_credentials()
        
        return new_user, "User created successfully"
    
    def authenticate_user(self, email, password):
        """Authenticate user with email and password"""
        user = self.find_user_by_email(email)
        if not user:
            return None, "User not found"
        
        if not user.get('is_active', True):
            return None, "Account is deactivated"
        
        if user['auth_type'] != 'email':
            return None, "Please use Google Sign-In for this account"
        
        if not self.verify_password(password, user['password']):
            return None, "Invalid password"
        
        # Update last login
        user['last_login'] = datetime.now().isoformat()
        self.save_credentials()
        
        return user, "Login successful"
    
    def authenticate_google_user(self, google_user_info):
        """Authenticate or create user from Google Sign-In"""
        email = google_user_info.get('email')
        name = google_user_info.get('name')
        
        if not email or not name:
            return None, "Invalid Google user information"
        
        # Check if user exists
        user = self.find_user_by_email(email)
        
        if user:
            # Update last login
            user['last_login'] = datetime.now().isoformat()
            self.save_credentials()
            return user, "Login successful"
        else:
            # Create new user
            return self.create_user(name, email, '', auth_type='google')
    
    def generate_session_token(self, user):
        """Generate JWT session token"""
        payload = {
            'user_id': user['id'],
            'email': user['email'],
            'name': user['name'],
            'exp': datetime.utcnow() + timedelta(hours=24),  # Token expires in 24 hours
            'iat': datetime.utcnow()
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        
        # Store session in memory/JSON
        self.credentials['sessions'][str(user['id'])] = {
            'token': token,
            'created_at': datetime.now().isoformat(),
            'user_id': user['id']
        }
        self.save_credentials()
        
        return token
    
    def verify_session_token(self, token):
        """Verify JWT session token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            user_id = payload['user_id']
            
            # Check if session exists
            if str(user_id) not in self.credentials['sessions']:
                return None, "Session not found"
            
            # Find user
            user = None
            for u in self.credentials['users']:
                if u['id'] == user_id:
                    user = u
                    break
            
            if not user or not user.get('is_active', True):
                return None, "User not found or inactive"
            
            return user, "Valid session"
            
        except jwt.ExpiredSignatureError:
            return None, "Session expired"
        except jwt.InvalidTokenError:
            return None, "Invalid session token"
    
    def logout_user(self, user_id):
        """Logout user by removing session"""
        if str(user_id) in self.credentials['sessions']:
            del self.credentials['sessions'][str(user_id)]
            self.save_credentials()
            return True
        return False
    
    def get_current_user_from_session(self):
        """Get current user from session token"""
        token = None
        
        # Try to get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        # Try to get token from session
        if not token:
            token = session.get('auth_token')
        
        if not token:
            return None
        
        user, message = self.verify_session_token(token)
        return user

# Authentication decorator
def login_required(auth_manager):
    """Decorator to require authentication"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = auth_manager.get_current_user_from_session()
            if not user:
                if request.is_json:
                    return jsonify({'error': 'Authentication required'}), 401
                else:
                    return redirect(url_for('home'))
            return f(user, *args, **kwargs)
        return decorated_function
    return decorator

def setup_auth_routes(app, auth_manager, api_prefix):
    """Setup authentication routes"""
    
    @app.route('/api/signup', methods=['POST'])
    def api_signup():
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            
            if not name or not email or not password:
                return jsonify({'error': 'All fields are required'}), 400
            
            # Validate email format (basic validation)
            if '@' not in email or '.' not in email.split('@')[1]:
                return jsonify({'error': 'Invalid email format'}), 400
            
            user, message = auth_manager.create_user(name, email, password)
            
            if user:
                return jsonify({
                    'message': message,
                    'user': {
                        'id': user['id'],
                        'name': user['name'],
                        'email': user['email']
                    }
                }), 201
            else:
                return jsonify({'error': message}), 400
                
        except Exception as e:
            print(f"!!! SIGNUP API ERROR: {e}")  # <-- ADD THIS LINE
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/login', methods=['POST'])
    def api_login():
        try:
            data = request.get_json()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            
            if not email or not password:
                return jsonify({'error': 'Email and password are required'}), 400
            
            user, message = auth_manager.authenticate_user(email, password)
            
            if user:
                # Generate session token
                token = auth_manager.generate_session_token(user)
                
                # Store token in session
                session['auth_token'] = token
                session['user_id'] = user['id']
                
                return jsonify({
                    'message': message,
                    'token': token,
                    'user': {
                        'id': user['id'],
                        'name': user['name'],
                        'email': user['email']
                    }
                }), 200
            else:
                return jsonify({'error': message}), 401
                
        except Exception as e:
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/google-auth', methods=['POST'])
    def api_google_auth():
        try:
            data = request.get_json()
            token = data.get('token')
            
            if not token:
                return jsonify({'error': 'Google token is required'}), 400
            
            # In a real implementation, you would verify the Google JWT token here
            # For now, we'll decode it without verification (NOT SECURE for production)
            try:
                import base64
                # Decode the JWT payload (this is just for demo - use proper verification in production)
                parts = token.split('.')
                payload = parts[1]
                # Add padding if needed
                payload += '=' * (4 - len(payload) % 4)
                decoded_payload = base64.urlsafe_b64decode(payload)
                google_user_info = json.loads(decoded_payload)
                
                user, message = auth_manager.authenticate_google_user(google_user_info)
                
                if user:
                    # Generate session token
                    session_token = auth_manager.generate_session_token(user)
                    
                    # Store token in session
                    session['auth_token'] = session_token
                    session['user_id'] = user['id']
                    
                    return jsonify({
                        'message': message,
                        'token': session_token,
                        'user': {
                            'id': user['id'],
                            'name': user['name'],
                            'email': user['email']
                        }
                    }), 200
                else:
                    return jsonify({'error': message}), 400
                    
            except Exception as e:
                return jsonify({'error': 'Invalid Google token'}), 400
                
        except Exception as e:
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/logout', methods=['POST'])
    def api_logout():
        try:
            user_id = session.get('user_id')
            if user_id:
                auth_manager.logout_user(user_id)
                session.clear()
            return jsonify({'message': 'Logged out successfully'}), 200
        except Exception as e:
            # Add this to print the real exception in logs
            print(f"Logout error: {e}")
            return jsonify({'error': 'Internal server error'}), 500


    
    @app.route('/api/me', methods=['GET'])
    def api_get_current_user():
        """Get current user information"""
        user = auth_manager.get_current_user_from_session()
        if user:
            return jsonify({
                'user': {
                    'id': user['id'],
                    'name': user['name'],
                    'email': user['email'],
                    'auth_type': user['auth_type'],
                    'last_login': user.get('last_login')
                }
            }), 200
        else:
            return jsonify({'error': 'Not authenticated'}), 401
    
    return auth_manager