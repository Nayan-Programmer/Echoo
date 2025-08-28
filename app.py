# app.py

from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for, session
from flask_dance.contrib.google import make_google_blueprint, google
from sympy import sympify, solve, simplify, pretty
from dotenv import dotenv_values
from groq import Groq
import requests, os

# Load environment variables
env = dotenv_values(".env")
Username = env.get("Username", "User")
AssistantName = env.get("AssistantName", "EchooAI")
GroqAPIKey = env.get("GroqAPIKey", "")
GoogleAPIKey = env.get("GoogleAPIKey", "")
GoogleCSEID = env.get("GoogleCSEID", "")
DeveloperName = env.get("DeveloperName", "Nayan")
FullInformation = env.get("FullInformation", "")

# Flask app aur session ko initialize karein
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.urandom(24) # Session suraksha ke liye

# Google OAuth credentials ko set karein
# Aapko in credentials ko Google Cloud Console se lena hoga
GOOGLE_CLIENT_ID = env.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = env.get("GOOGLE_CLIENT_SECRET", "")

# Flask-Dance Google blueprint banayein
# scope mein user ki profile aur email access karne ki permission di gayi hai
google_bp = make_google_blueprint(
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    scope=["https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"],
)

# Blueprint ko app ke saath register karein
app.register_blueprint(google_bp, url_prefix="/login")

# Initialize Groq client
client = Groq(api_key=GroqAPIKey)

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
def RealtimeEngine(prompt):
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
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": f"You are {AssistantName}, an AI built by {DeveloperName}."},
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
    if not google.authorized:
        # User logged in nahi hai, unko login page par redirect karein
        return redirect(url_for("google.login"))

    # Login hone ke baad, user ki profile data lein
    try:
        resp = google.get("/oauth2/v2/userinfo")
        resp.raise_for_status()
        profile_data = resp.json()
        
        # Session mein user data store karein
        session['user'] = profile_data
        
        # index.html ko render karein, user data ke saath
        return render_template("index.html", user=profile_data)
    except Exception as e:
        print(f"Error fetching profile: {e}")
        return redirect(url_for("google.login"))

@app.route("/chat", methods=["POST"])
def chat():
    # Sirf authorized users ko chat karne dein
    if not google.authorized:
        return jsonify({"reply": "Please log in to chat."}), 401

    data = request.get_json()
    user_prompt = data.get("message", "")
    if not user_prompt:
        return jsonify({"reply": "Please enter a message."}), 400
    
    reply = RealtimeEngine(user_prompt)
    return jsonify({"reply": reply})

@app.route("/logout")
def logout():
    # Session se user data hata dein aur login page par wapas le jayein
    session.clear()
    return redirect(url_for("google.login"))

# Serve static logo if needed
@app.route('/logo/<path:filename>')
def logo(filename):
    return send_from_directory('static', filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
