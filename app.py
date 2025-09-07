from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from sympy import sympify, solve, simplify, pretty
from dotenv import dotenv_values
from groq import Groq
import requests, os
from authlib.integrations.flask_client import OAuth

# Load environment variables
env = dotenv_values(".env")
AssistantName = env.get("AssistantName", "EchooAI")
GroqAPIKey = env.get("GroqAPIKey", "")
GoogleAPIKey = env.get("GoogleAPIKey", "")
GoogleCSEID = env.get("GoogleCSEID", "")
DeveloperName = env.get("DeveloperName", "Nayan")
FullInformation = env.get("FullInformation", "")
StabilityKey = env.get("STABILITY_API_KEY", "")   # NEW

GoogleClientID = env.get("GOOGLE_CLIENT_ID")
GoogleClientSecret = env.get("GOOGLE_CLIENT_SECRET")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.urandom(24)

# OAuth
oauth = OAuth(app)
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
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": f"You are {AssistantName}, built by {DeveloperName}. Current user: {user_name}."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        print(e)
        return f"Groq backend error: {e}"

# --- Routes ---
@app.route("/")
def home():
    user_info = session.get('user_info')
    chat_sessions = session.get('chat_sessions', [])
    active_chat = session.get('active_chat')
    return render_template("index.html",
                           assistant_name=AssistantName,
                           user_info=user_info,
                           chat_sessions=chat_sessions,
                           active_chat=active_chat)

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
        session['chat_sessions'] = []
        session['active_chat'] = None
        session.pop('nonce', None)
        return redirect(url_for('home'))
    except Exception as e:
        print(f"Authentication Error: {e}")
        return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
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

    if 'chat_sessions' not in session:
        session['chat_sessions'] = []
    if not session.get('active_chat'):
        chat_id = str(len(session['chat_sessions']) + 1)
        session['chat_sessions'].append({"id": chat_id, "title": f"Chat {chat_id}", "messages": []})
        session['active_chat'] = chat_id

    for chat in session['chat_sessions']:
        if chat['id'] == session['active_chat']:
            chat['messages'].append({"sender": "user", "message": user_prompt})
            reply = RealtimeEngine(user_prompt, user_info)
            chat['messages'].append({"sender": "ai", "message": reply})
            session.modified = True
            return jsonify({"reply": reply})

    return jsonify({"reply": "Error: Active chat not found."}), 500

# --- Image Generation with Stability.ai ---
@app.route("/image-gen", methods=["POST"])
def image_gen():
    user_info = session.get('user_info')
    if not user_info:
        return jsonify({"error": "Please log in with Google"}), 401

    data = request.get_json()
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "Prompt is required."}), 400

    try:
        headers = {"Authorization": f"Bearer {StabilityKey}"}
        response = requests.post(
            "https://api.stability.ai/v1/generation/stable-diffusion-v1-5/text-to-image",
            headers=headers,
            json={"text_prompts": [{"text": prompt}], "cfg_scale": 7, "steps": 30}
        )

        if response.status_code == 200:
            img_base64 = response.json()["artifacts"][0]["base64"]
            return jsonify({"images": ["data:image/png;base64," + img_base64]})
        else:
            return jsonify({"error": "Stability API failed", "details": response.text}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/logo/<path:filename>')
def logo(filename):
    return send_from_directory('static', filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
