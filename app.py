from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from sympy import sympify, solve, simplify, pretty
from dotenv import dotenv_values
from groq import Groq
import requests, os
from authlib.integrations.flask_client import OAuth
from datetime import datetime

# Load environment variables
env = dotenv_values(".env")
Username = env.get("Username", "User")
AssistantName = env.get("AssistantName", "EchooAI")
GroqAPIKey = env.get("GroqAPIKey", "")
GoogleAPIKey = env.get("GoogleAPIKey", "")
GoogleCSEID = env.get("GoogleCSEID", "")
DeveloperName = env.get("DeveloperName", "Nayan")
FullInformation = env.get("FullInformation", "")
HF_API_KEY = env.get("HuggingFaceAPIKey", "")

# Google OAuth credentials
GoogleClientID = env.get("GOOGLE_CLIENT_ID")
GoogleClientSecret = env.get("GOOGLE_CLIENT_SECRET")

# Initialize Flask app
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.urandom(24)

# Initialize Authlib OAuth
oauth = OAuth(app)

# Register Google OAuth
oauth.register(
    name='google',
    client_id=GoogleClientID,
    client_secret=GoogleClientSecret,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

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

# --- AI Engine ---
def RealtimeEngine(prompt, user_info=None):
    user_name = user_info.get('name', 'User') if user_info else 'User'

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
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",   # ⚡ Faster than whisper
            messages=[
                {"role": "system", "content": f"You are {AssistantName}, an AI built by {DeveloperName}. The current user's name is {user_name}."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        print(e)
        return f"Groq backend error: {e}"

# --- Image Generation (HuggingFace SDXL) ---
def generate_image(prompt):
    try:
        url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
        headers = {"Authorization": f"Bearer {HF_API_KEY}"}
        payload = {"inputs": f"{prompt}, ultra high quality, 4k, realistic"}
        
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        if r.status_code != 200 or "image" not in r.headers.get("Content-Type", ""):
            return None
        
        # Save in static folder
        filename = f"generated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = os.path.join("static", filename)
        with open(filepath, "wb") as f:
            f.write(r.content)
        return f"/static/{filename}"
    except Exception as e:
        print(f"Image API error: {e}")
        return None

# --- Routes ---
@app.route("/", methods=["GET"])
def home():
    user_info = session.get('user_info')
    chat_history = session.get('chat_history', [])
    return render_template("index.html", assistant_name=AssistantName, user_info=user_info, chat_history=chat_history)

@app.route('/google-login')
def google_login():
    redirect_uri = url_for('google_auth', _external=True)
    session['nonce'] = os.urandom(32).hex()
    return oauth.google.authorize_redirect(redirect_uri, nonce=session['nonce'])

@app.route('/google/auth/')
def google_auth():
    try:
        token = oauth.google.authorize_access_token()
        user = oauth.google.parse_id_token(token, nonce=session.get('nonce'))
        session['user_info'] = user
        session['chat_history'] = []
        session.pop('nonce', None)
        return redirect(url_for('home'))
    except Exception as e:
        print(f"Authentication Error: {e}")
        return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.pop('user_info', None)
    session.pop('chat_history', None)
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
    
    chat_history = session.get('chat_history', [])
    chat_history.append({"sender": "user", "message": user_prompt})
    session['chat_history'] = chat_history

    reply = RealtimeEngine(user_prompt, user_info)

    chat_history.append({"sender": "ai", "message": reply})
    session['chat_history'] = chat_history
    
    return jsonify({"reply": reply})

# --- Image Generation Route ---
@app.route("/image-gen", methods=["POST"])
def image_gen():
    data = request.get_json()
    prompt = data.get("prompt", "")
    if not prompt:
        return jsonify({"images": [], "error": "No prompt given"})
    
    img_url = generate_image(prompt)
    if img_url:
        return jsonify({"images": [img_url]})
    return jsonify({"images": [], "error": "Image generation failed"})

@app.route('/logo/<path:filename>')
def logo(filename):
    return send_from_directory('static', filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
