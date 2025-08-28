from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from sympy import sympify, solve, simplify, pretty
from dotenv import dotenv_values
from groq import Groq
import requests, os
from authlib.integrations.flask_client import OAuth
import time

# Load environment variables
env = dotenv_values(".env")
Username = env.get("Username", "User")
AssistantName = env.get("AssistantName", "EchooAI")
GroqAPIKey = env.get("GroqAPIKey", "")
GoogleAPIKey = env.get("GoogleAPIKey", "")
GoogleCSEID = env.get("GoogleCSEID", "")
DeveloperName = env.get("DeveloperName", "Nayan")
FullInformation = env.get("FullInformation", "")

# Google OAuth credentials
GoogleClientID = env.get("GOOGLE_CLIENT_ID")
GoogleClientSecret = env.get("GOOGLE_CLIENT_SECRET")

# Initialize Flask app
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.urandom(24)

# Initialize Authlib OAuth
oauth = OAuth(app)

# Register the Google OAuth client
oauth.register(
    name='google',
    client_id=GoogleClientID,
    client_secret=GoogleClientSecret,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# --- Math Solver ---
def solve_math(query):
    """
    Solves mathematical equations using the sympy library.
    """
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
def GoogleSearch(query):
    """
    Performs a custom Google Search and returns snippets.
    """
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {"q": query, "key": GoogleAPIKey, "cx": GoogleCSEID}
        r = requests.get(url, params=params)
        data = r.json()
        if "items" in data:
            return "\n".join([item["snippet"] for item in data["items"][:3]])
        return "No results found."
    except Exception as e:
        return f"(Search Error: {e})"

# --- AI Engine ---
def RealtimeEngine(prompt, chat_history, user_name):
    """
    Main AI engine that handles various types of queries.
    It now includes chat history for context.
    """
    # Math queries
    if any(op in prompt for op in ["+", "-", "*", "/", "=", "solve", "integrate", "derivative", "diff", "factor", "limit"]):
        return solve_math(prompt)

    # Google search
    if prompt.lower().startswith("search:"):
        query = prompt.replace("search:", "").strip()
        return GoogleSearch(query)

    # Developer info
    if "who is your developer" in prompt.lower() or "who created you" in prompt.lower():
        return f"My developer is {DeveloperName}. {FullInformation}"

    # Groq AI
    try:
        client = Groq(api_key=GroqAPIKey)
        
        # Build the messages list for the API call
        messages = [
            # System message with user's name for context
            {"role": "system", "content": f"You are {AssistantName}, an AI built by {DeveloperName}. The current user is {user_name}. Maintain a conversational and friendly tone."},
            # Add previous chat history
            *chat_history,
            # Add the new user prompt
            {"role": "user", "content": prompt}
        ]
        
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=messages,
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
    # Get current chat history and all previous chats from session
    current_chat = session.get('current_chat', [])
    all_chats = session.get('all_chats', [])
    return render_template("index.html", 
                           assistant_name=AssistantName, 
                           user_info=user_info, 
                           current_chat=current_chat,
                           all_chats=all_chats)

# Route to initiate Google login
@app.route('/google-login')
def google_login():
    redirect_uri = url_for('google_auth', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

# Route to handle Google's callback
@app.route('/google/auth/')
def google_auth():
    try:
        token = oauth.google.authorize_access_token()
        user = oauth.google.parse_id_token(token, nonce=session.get('nonce'))
        
        session['user_info'] = user
        session.pop('nonce', None)
        
        # Clear current chat on login
        session.pop('current_chat', None)
        return redirect(url_for('home'))
    except Exception as e:
        print(f"Authentication Error: {e}")
        return redirect(url_for('home'))

# Logout route
@app.route('/logout')
def logout():
    session.pop('user_info', None)
    session.pop('current_chat', None)
    session.pop('all_chats', None)
    return redirect(url_for('home'))

@app.route("/chat", methods=["POST"])
def chat():
    user_info = session.get('user_info')
    if not user_info:
        return jsonify({"reply": "Please log in with Google to use the chat."}), 401

    data = request.get_json()
    user_prompt = data.get("message", "")
    if not user_prompt:
        return jsonify({"reply": "Please enter a message."}), 400

    user_name = user_info.get('given_name', 'User')

    current_chat = session.get('current_chat', [])
    
    reply = RealtimeEngine(user_prompt, current_chat, user_name)

    current_chat.append({"role": "user", "content": user_prompt})
    current_chat.append({"role": "assistant", "content": reply})

    session['current_chat'] = current_chat
    
    return jsonify({"reply": reply})

@app.route("/save-chat", methods=["POST"])
def save_chat():
    """Saves the current chat history to the list of all chats."""
    current_chat = session.get('current_chat', [])
    if current_chat:
        all_chats = session.get('all_chats', [])
        # Create a title for the chat, e.g., the first user message
        title = current_chat[0]['content'][:30] + '...' if len(current_chat[0]['content']) > 30 else current_chat[0]['content']
        chat_id = int(time.time()) # Unique ID based on timestamp
        
        all_chats.append({
            'id': chat_id,
            'title': title,
            'history': current_chat
        })
        session['all_chats'] = all_chats
    return jsonify({"status": "Chat saved."})

@app.route("/new-chat", methods=["POST"])
def new_chat():
    """Clears the current chat history to start a new conversation."""
    session.pop('current_chat', None)
    return jsonify({"status": "New chat started."})

@app.route("/load-chat/<int:chat_id>", methods=["GET"])
def load_chat(chat_id):
    """Loads a specific chat from the all_chats list into the current_chat session."""
    all_chats = session.get('all_chats', [])
    chat_to_load = next((chat for chat in all_chats if chat['id'] == chat_id), None)
    if chat_to_load:
        session['current_chat'] = chat_to_load['history']
        return jsonify({"status": "Chat loaded.", "history": chat_to_load['history']})
    return jsonify({"status": "Chat not found."}), 404

# Serve static logo
@app.route('/logo/<path:filename>')
def logo(filename):
    return send_from_directory('static', filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
