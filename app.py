from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for, g
from sympy import sympify, solve, simplify, pretty
from dotenv import dotenv_values
from groq import Groq
import requests, os, sqlite3, json
from authlib.integrations.flask_client import OAuth

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

# --- Database Setup ---
DATABASE = 'chat_history.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                chat_title TEXT,
                history TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.commit()

@app.before_request
def setup_database():
    init_db()

# --- Utility Functions ---
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

def GoogleSearch(query):
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

def RealtimeEngine(prompt, chat_history=[]):
    groq_history = [{"role": "system", "content": f"You are {AssistantName}, an AI built by {DeveloperName}."},]
    for msg in chat_history:
        groq_history.append({"role": msg['role'], "content": msg['content']})
    groq_history.append({"role": "user", "content": prompt})

    if any(op in prompt for op in ["+", "-", "*", "/", "=", "solve", "integrate", "derivative", "diff", "factor", "limit"]):
        return solve_math(prompt)

    if prompt.lower().startswith("search:"):
        query = prompt.replace("search:", "").strip()
        return GoogleSearch(query)

    if "who is your developer" in prompt.lower() or "who created you" in prompt.lower():
        return f"My developer is {DeveloperName}. {FullInformation}"

    try:
        client = Groq(api_key=GroqAPIKey)
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=groq_history,
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
    previous_chats = []
    if user_info:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id, chat_title FROM chats WHERE user_email = ? ORDER BY created_at DESC", (user_info['email'],))
        previous_chats = cursor.fetchall()
    return render_template("index.html", assistant_name=AssistantName, user_info=user_info, previous_chats=previous_chats)

@app.route('/google-login')
def google_login():
    redirect_uri = url_for('google_auth', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@app.route('/google/auth/')
def google_auth():
    try:
        token = oauth.google.authorize_access_token()
        user = oauth.google.parse_id_token(token)
        
        session['user_info'] = user

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM chats WHERE user_email = ?", (user['email'],))
        existing_chat = cursor.fetchone()

        if not existing_chat:
            default_history = json.dumps([{"role": "assistant", "content": f"Hi {user.get('given_name', 'User')}! How can I help you today?"}])
            cursor.execute("INSERT INTO chats (user_email, chat_title, history) VALUES (?, ?, ?)", 
                           (user['email'], 'New Chat', default_history))
            db.commit()
            
        return redirect(url_for('home'))
    except Exception as e:
        print(f"Authentication Error: {e}")
        return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.pop('user_info', None)
    return redirect(url_for('home'))

@app.route("/chat-history/<int:chat_id>", methods=["GET"])
def get_chat_history(chat_id):
    user_info = session.get('user_info')
    if not user_info:
        return jsonify({"error": "Please log in to view chat history."}), 401
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT history FROM chats WHERE id = ? AND user_email = ?", (chat_id, user_info['email']))
    chat = cursor.fetchone()
    
    if chat:
        history = json.loads(chat['history'])
        return jsonify({"history": history})
    
    return jsonify({"error": "Chat not found or access denied."}), 404

@app.route("/new-chat", methods=["POST"])
def new_chat():
    user_info = session.get('user_info')
    if not user_info:
        return jsonify({"error": "Please log in to create a new chat."}), 401
    
    db = get_db()
    cursor = db.cursor()
    initial_message = f"Hi {user_info.get('given_name', 'User')}! How can I help you today?"
    default_history = json.dumps([{"role": "assistant", "content": initial_message}])
    
    cursor.execute("INSERT INTO chats (user_email, chat_title, history) VALUES (?, ?, ?)", 
                   (user_info['email'], 'New Chat', default_history))
    db.commit()
    new_chat_id = cursor.lastrowid
    
    return jsonify({"chat_id": new_chat_id, "history": json.loads(default_history)})

@app.route("/chat", methods=["POST"])
def chat():
    user_info = session.get('user_info')
    if not user_info:
        return jsonify({"reply": "Please log in with Google to use the chat."}), 401

    data = request.get_json()
    user_prompt = data.get("message", "")
    chat_id = data.get("chat_id")
    if not user_prompt:
        return jsonify({"reply": "Please enter a message."}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT history FROM chats WHERE id = ? AND user_email = ?", (chat_id, user_info['email']))
    chat = cursor.fetchone()
    if not chat:
        return jsonify({"reply": "Chat not found."}), 404
        
    chat_history = json.loads(chat['history'])
    reply = RealtimeEngine(user_prompt, chat_history)

    chat_history.append({"role": "user", "content": user_prompt})
    chat_history.append({"role": "assistant", "content": reply})
    
    cursor.execute("UPDATE chats SET history = ? WHERE id = ?", (json.dumps(chat_history), chat_id))
    db.commit()
    
    return jsonify({"reply": reply})

# Serve static logo
@app.route('/logo/<path:filename>')
def logo(filename):
    return send_from_directory('static', filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
