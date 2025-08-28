import os
import sqlite3
import json
from flask import Flask, render_template, redirect, url_for, session, request, jsonify
from authlib.integrations.flask_client import OAuth
from authlib.common.security import generate_token
from groq import Groq  # Import the Groq library

# Load environment variables from a .env file
from dotenv import load_dotenv
load_dotenv()

# --- Configuration ---
app = Flask(__name__)
# It's crucial to set a secret key for session management
app.secret_key = os.urandom(24)

# Configure Authlib for Google OAuth
oauth = OAuth(app)
oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# Configure Groq client
groq_client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

# --- Database Setup ---
DATABASE = 'chat_history.db'

def get_db():
    """Connects to the specified database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
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

# --- Groq API Call Function ---
def get_groq_response(messages):
    """Sends a list of messages to the Groq API and returns the response."""
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=messages,
            model="llama3-8b-8192",  # You can choose a different model here
            stream=False,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Error calling Groq API: {e}")
        return "Sorry, I am unable to respond at the moment."

# --- Routes ---

@app.route('/')
def home():
    """Renders the home page. Redirects to login if user is not authenticated."""
    user_info = session.get('user_info')
    if not user_info:
        return render_template('login.html')
    
    user_email = user_info['email']
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute("SELECT id, chat_title, history FROM chats WHERE user_email = ?", (user_email,))
        chats = cursor.fetchall()
        
    return render_template('index.html', user=user_info, chats=chats)

@app.route('/login')
def login():
    """Starts the Google OAuth flow."""
    session['nonce'] = generate_token()
    redirect_uri = url_for('google_auth', _external=True)
    return oauth.google.authorize_redirect(redirect_uri, nonce=session['nonce'])

@app.route('/google/auth/')
def google_auth():
    """Callback route for Google authentication."""
    try:
        token = oauth.google.authorize_access_token(nonce=session.get('nonce'))
        user = oauth.google.parse_id_token(token)
        session['user_info'] = user

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
            
        return redirect(url_for('home'))
    except Exception as e:
        session.pop('user_info', None)
        return redirect(url_for('home'))

@app.route('/logout')
def logout():
    """Clears the session and logs the user out."""
    session.pop('user_info', None)
    return redirect(url_for('home'))

@app.route('/chat', methods=['POST'])
def chat():
    """Handles the chat conversation with the Groq API."""
    user_info = session.get('user_info')
    if not user_info:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    user_message = data.get('message')
    chat_id = data.get('chat_id')
    user_email = user_info['email']

    if not user_message:
        return jsonify({'error': 'Message cannot be empty'}), 400

    with get_db() as db:
        cursor = db.cursor()
        cursor.execute("SELECT history FROM chats WHERE id = ? AND user_email = ?", (chat_id, user_email))
        chat_row = cursor.fetchone()

        if not chat_row:
            return jsonify({'error': 'Chat not found'}), 404

        history = json.loads(chat_row['history'])

        # Add the user's message to the history
        history.append({"role": "user", "content": user_message})

        # Get response from Groq
        groq_response = get_groq_response(history)

        # Add the assistant's response to the history
        history.append({"role": "assistant", "content": groq_response})

        # Update the database
        new_history_json = json.dumps(history)
        cursor.execute("UPDATE chats SET history = ? WHERE id = ?", (new_history_json, chat_id))
        db.commit()

        return jsonify({'response': groq_response})

if __name__ == '__main__':
    app.run(debug=True)
