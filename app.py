import os
import sqlite3
import json
from flask import Flask, render_template, redirect, url_for, session
from authlib.integrations.flask_client import OAuth

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# --- Configuration ---
app = Flask(__name__)
# It's crucial to set a secret key for session management
app.secret_key = os.urandom(24)

oauth = OAuth(app)
oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'client_id': os.environ.get('GOOGLE_CLIENT_ID'),
        'client_secret': os.environ.get('GOOGLE_CLIENT_SECRET'),
        'scope': 'openid email profile'
    }
)

# --- Database Setup ---
DATABASE = 'chat_history.db'

def get_db():
    """Connects to the specified database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn

def create_table():
    """Creates the necessary chats table if it doesn't exist."""
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                chat_title TEXT NOT NULL,
                history TEXT NOT NULL
            );
        """)
        db.commit()

# Ensure the table exists when the app starts
create_table()

# --- Routes ---

@app.route('/')
def home():
    """Renders the home page. Redirects to login if user is not authenticated."""
    user_info = session.get('user_info')
    if not user_info:
        return render_template('login.html')
    
    # Get user's chats from the database
    user_email = user_info['email']
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute("SELECT id, chat_title, history FROM chats WHERE user_email = ?", (user_email,))
        chats = cursor.fetchall()
        
    return render_template('index.html', user=user_info, chats=chats)

@app.route('/login')
def login():
    """Starts the Google OAuth flow."""
    redirect_uri = url_for('google_auth', _external=True)
    # Redirect the user to the Google login page
    return oauth.google.authorize_redirect(redirect_uri)

@app.route('/google/auth/')
def google_auth():
    """Callback route for Google authentication."""
    try:
        # Step 1: Authorize access token
        token = oauth.google.authorize_access_token()
        print("Token received successfully.")
        
        # Step 2: Parse user information from the ID token
        user = oauth.google.parse_id_token(token)
        print("User information parsed successfully.")
        
        # Step 3: Store user information in the session
        session['user_info'] = user
        print(f"Session updated with user: {user.get('given_name')}")

        # Step 4: Check for existing chat and create a new one if not found
        user_email = user['email']
        with get_db() as db:
            cursor = db.cursor()
            cursor.execute("SELECT id FROM chats WHERE user_email = ?", (user_email,))
            existing_chat = cursor.fetchone()

            if not existing_chat:
                default_history = json.dumps([
                    {"role": "assistant", "content": f"Hi {user.get('given_name', 'User')}! How can I help you today?"}
                ])
                cursor.execute("INSERT INTO chats (user_email, chat_title, history) VALUES (?, ?, ?)", 
                               (user_email, 'New Chat', default_history))
                db.commit()
                print("New chat created for the user.")
            
        return redirect(url_for('home'))
    except Exception as e:
        # Detailed error logging for debugging
        print("-" * 50)
        print("Authentication Error Occurred:")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {e}")
        session.pop('user_info', None)  # Clear any partial session data
        print("Session data cleared.")
        print("-" * 50)
        return redirect(url_for('home'))

@app.route('/logout')
def logout():
    """Clears the session and logs the user out."""
    session.pop('user_info', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)

