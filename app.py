import os
import requests
import json
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from dotenv import dotenv_values
from groq import Groq
from sympy import sympify, solve, simplify, pretty
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
import firebase_admin
from firebase_admin import credentials, auth, firestore

# Load environment variables
env = dotenv_values(".env")
USERNAME = env.get("Username", "User")
ASSISTANT_NAME = env.get("AssistantName", "EchooAI")
GROQ_API_KEY = env.get("GroqAPIKey", "")
GOOGLE_API_KEY = env.get("GoogleAPIKey", "")
GOOGLE_CSE_ID = env.get("GoogleCSEID", "")
DEVELOPER_NAME = env.get("DeveloperName", "Nayan")
FULL_INFORMATION = env.get("FullInformation", "")
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = ["https://www.googleapis.com/auth/userinfo.email", "openid", "https://www.googleapis.com/auth/userinfo.profile"]

# Ensure all necessary environment variables are set
if not all([GROQ_API_KEY, GOOGLE_API_KEY, GOOGLE_CSE_ID]):
    raise ValueError("Missing required environment variables. Check your .env file.")

# Initialize Groq client
groq_client = Groq(api_key=GROQ_API_KEY)
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.urandom(24)

# Use a memory-based session for this example
# In a production app, you would use something more robust like Flask-Session with a database
from flask.sessions import SessionInterface
from werkzeug.datastructures import CallbackDict

class SimpleSession(CallbackDict, SessionInterface):
    def __init__(self, initial=None):
        def on_update(d):
            self.modified = True
        CallbackDict.__init__(self, initial, on_update)
        self.modified = False

    def open(self, app, request):
        return SimpleSession(initial=request.cookies.get('session'))

    def save(self, app, session, response):
        if session.modified:
            response.set_cookie('session', json.dumps(dict(session)))

app.session_interface = SimpleSession()

# Initialize Firebase Admin SDK
FIREBASE_CREDENTIALS = env.get("FIREBASE_ADMIN_SDK_CONFIG")
if not FIREBASE_CREDENTIALS:
    raise ValueError("Missing FIREBASE_ADMIN_SDK_CONFIG in .env file.")
firebase_credentials = credentials.Certificate(json.loads(FIREBASE_CREDENTIALS))
firebase_admin.initialize_app(firebase_credentials)
db = firestore.client()

# --- Utility Functions ---
def get_or_create_user(user_email, user_id, display_name):
    """Fetches or creates a user in Firebase Auth and returns their UID."""
    try:
        user = auth.get_user_by_email(user_email)
        return user.uid
    except auth.AuthError:
        user = auth.create_user(uid=user_id, email=user_email, display_name=display_name)
        return user.uid

# --- Math Solver ---
def solve_math(query):
    try:
        expr = sympify(query)
        simplified = simplify(expr)
        solution = solve(expr)
        return (
            f"Step 1: Expression → {pretty(expr)}\n"
            f"Step 2: Simplified → {pretty(simplified)}\n"
            f"Step 3: Solution → {solution if solution else 'No closed form solution'}"
        )
    except Exception as e:
        return f"Math Error: {e}"

# --- Google Search ---
def google_search(query):
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {"q": query, "key": GOOGLE_API_KEY, "cx": GOOGLE_CSE_ID}
        r = requests.get(url, params=params)
        data = r.json()
        if "items" in data:
            return "\n".join([item["snippet"] for item in data["items"][:3]])
        return "No results found."
    except Exception as e:
        return f"(Search Error: {e})"

# --- AI Engine ---
def realtime_engine(prompt):
    # Math queries
    if any(op in prompt for op in ["+", "-", "*", "/", "=", "solve", "integrate", "derivative", "diff", "factor", "limit"]):
        return solve_math(prompt)

    # Google search
    if prompt.lower().startswith("search:"):
        query = prompt.replace("search:", "").strip()
        return google_search(query)

    # Developer info
    if "who is your developer" in prompt.lower() or "who created you" in prompt.lower():
        return f"My developer is {DEVELOPER_NAME}. {FULL_INFORMATION}"

    # Groq AI
    try:
        response = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": f"You are {ASSISTANT_NAME}, an AI built by {DEVELOPER_NAME}."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        print(e)
        return f"Groq backend error: {e}"

# --- Routes ---
@app.route("/", methods=["GET"])
def home():
    user_info = session.get('user_info')
    all_chats = []
    current_chat = []

    if user_info:
        user_id = user_info['uid']
        # Load all previous chat titles for the sidebar
        chat_docs = db.collection('users').document(user_id).collection('chats').stream()
        for doc in chat_docs:
            chat_data = doc.to_dict()
            all_chats.append({
                "id": doc.id,
                "title": chat_data.get("title", "Untitled Chat")
            })

        # Load the current chat from the session or default to a new one
        current_chat_id = session.get('current_chat_id')
        if current_chat_id:
            chat_doc = db.collection('users').document(user_id).collection('chats').document(current_chat_id).get()
            if chat_doc.exists:
                current_chat = chat_doc.to_dict().get('history', [])
            else:
                session.pop('current_chat_id', None)
        
    return render_template(
        "index.html", 
        assistant_name=ASSISTANT_NAME, 
        developer_name=DEVELOPER_NAME,
        user_info=user_info,
        all_chats=all_chats,
        current_chat=current_chat
    )

@app.route("/chat", methods=["POST"])
def chat():
    user_info = session.get('user_info')
    if not user_info:
        return jsonify({"reply": "Please log in to chat."}), 401

    data = request.get_json()
    user_prompt = data.get("message", "")
    if not user_prompt:
        return jsonify({"reply": "Please enter a message."}), 400

    reply = realtime_engine(user_prompt)
    
    # Update the in-memory chat history
    current_chat = session.get('chat_history', [])
    current_chat.append({"role": "user", "content": user_prompt})
    current_chat.append({"role": "assistant", "content": reply})
    session['chat_history'] = current_chat
    
    return jsonify({"reply": reply})

@app.route("/new-chat", methods=["POST"])
def new_chat():
    user_info = session.get('user_info')
    if not user_info:
        return jsonify({"success": False})

    session.pop('chat_history', None)
    session.pop('current_chat_id', None)
    return jsonify({"success": True})

@app.route("/save-chat", methods=["POST"])
def save_chat():
    user_info = session.get('user_info')
    if not user_info:
        return jsonify({"success": False, "message": "Not logged in."})

    user_id = user_info['uid']
    chat_history = session.get('chat_history', [])

    if not chat_history:
        return jsonify({"success": False, "message": "No chat history to save."})

    current_chat_id = session.get('current_chat_id')
    chat_title = chat_history[0]['content'][:30] if chat_history else "New Chat"

    chat_doc_ref = db.collection('users').document(user_id).collection('chats')
    
    if current_chat_id:
        # Update existing chat
        doc_ref = chat_doc_ref.document(current_chat_id)
        doc_ref.set({
            "title": chat_title,
            "history": chat_history,
            "last_updated": firestore.SERVER_TIMESTAMP
        })
        return jsonify({"success": True, "message": "Chat updated."})
    else:
        # Save as a new chat
        doc_ref = chat_doc_ref.add({
            "title": chat_title,
            "history": chat_history,
            "created_at": firestore.SERVER_TIMESTAMP,
            "last_updated": firestore.SERVER_TIMESTAMP
        })
        session['current_chat_id'] = doc_ref.id
        return jsonify({"success": True, "message": "Chat saved.", "chat_id": doc_ref.id})

@app.route("/load-chat/<chat_id>", methods=["GET"])
def load_chat(chat_id):
    user_info = session.get('user_info')
    if not user_info:
        return jsonify({"success": False, "message": "Not logged in."})
    
    user_id = user_info['uid']
    chat_doc = db.collection('users').document(user_id).collection('chats').document(chat_id).get()
    
    if chat_doc.exists:
        chat_data = chat_doc.to_dict()
        session['chat_history'] = chat_data.get('history', [])
        session['current_chat_id'] = chat_id
        return jsonify({"success": True, "message": "Chat loaded."})
    else:
        return jsonify({"success": False, "message": "Chat not found."}), 404

@app.route('/google-login')
def google_login():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=url_for('callback', _external=True)
    )
    authorization_url, state = flow.authorization_url()
    session['state'] = state
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    state = session['state']
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for('callback', _external=True)
    )
    flow.fetch_token(authorization_response=request.url)
    credentials_obj = flow.credentials
    user_info_service = requests.get('https://www.googleapis.com/oauth2/v3/userinfo',
                                    headers={'Authorization': f'Bearer {credentials_obj.token}'})
    user_info = user_info_service.json()
    
    # Get or create the user in Firebase Auth
    firebase_uid = get_or_create_user(user_info['email'], user_info['sub'], user_info['name'])
    
    # Create a Firebase custom token
    custom_token = auth.create_custom_token(firebase_uid)
    
    session['user_info'] = {
        'uid': firebase_uid,
        'name': user_info.get('given_name', user_info.get('name')),
        'email': user_info['email']
    }
    
    # Pass the custom token to the frontend
    return redirect(url_for('home', custom_token=custom_token.decode("utf-8")))

@app.route('/logout')
def logout():
    session.pop('user_info', None)
    session.pop('chat_history', None)
    session.pop('current_chat_id', None)
    return redirect(url_for('home'))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
