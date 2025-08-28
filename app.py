from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from sympy import sympify, solve, simplify, pretty
from dotenv import dotenv_values
from groq import Groq
import requests, os
from authlib.integrations.flask_client import OAuth

# Load environment variables from .env file
env = dotenv_values(".env")
Username = env.get("Username", "User")
AssistantName = env.get("AssistantName", "EchooAI")
GroqAPIKey = env.get("GroqAPIKey", "")
GoogleAPIKey = env.get("GoogleAPIKey", "")
GoogleCSEID = env.get("GoogleCSEID", "")
DeveloperName = env.get("DeveloperName", "Nayan")
FullInformation = env.get("FullInformation", "")

# Google OAuth credentials from .env
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
# Now accepts chat history and user name
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
    # Get chat history from session, default to empty list if not found
    chat_history = session.get('chat_history', [])
    return render_template("index.html", 
                           assistant_name=AssistantName, 
                           user_info=user_info, 
                           chat_history=chat_history)

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
        
        # Redirect to home page after successful login
        return redirect(url_for('home'))
    except Exception as e:
        print(f"Authentication Error: {e}")
        return redirect(url_for('home'))

# Logout route
@app.route('/logout')
def logout():
    # Clear both user info and chat history from the session
    session.pop('user_info', None)
    session.pop('chat_history', None)
    return redirect(url_for('home'))

@app.route("/chat", methods=["POST"])
def chat():
    user_info = session.get('user_info')
    # Check if user is logged in
    if not user_info:
        return jsonify({"reply": "Please log in with Google to use the chat."}), 401

    data = request.get_json()
    user_prompt = data.get("message", "")
    if not user_prompt:
        return jsonify({"reply": "Please enter a message."}), 400

    # Get user's first name, or default to 'User'
    user_name = user_info.get('given_name', 'User')

    # Get chat history from session
    chat_history = session.get('chat_history', [])
    
    # Get the AI's reply, passing the history and user name
    reply = RealtimeEngine(user_prompt, chat_history, user_name)

    # Append user's message and AI's reply to history
    chat_history.append({"role": "user", "content": user_prompt})
    chat_history.append({"role": "assistant", "content": reply})

    # Save the updated history back to the session
    session['chat_history'] = chat_history
    
    return jsonify({"reply": reply})

# Serve static logo if needed
@app.route('/logo/<path:filename>')
def logo(filename):
    return send_from_directory('static', filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
