from flask import Flask, render_template, redirect, url_for, session, request, jsonify
from flask_dance.contrib.google import make_google_blueprint, google
from sympy import sympify, simplify, solve, pretty
from dotenv import dotenv_values
from groq import Groq
import os, json

# --- Load environment variables ---
env = dotenv_values(".env")
AssistantName = env.get("AssistantName","EchooAI")
GroqAPIKey = env.get("GroqAPIKey","")
DeveloperName = env.get("DeveloperName","Nayan")
FullInformation = env.get("FullInformation","")

client = Groq(api_key=GroqAPIKey)

# --- Flask Setup ---
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY","supersecretkey")

# --- Google OAuth Setup ---
blueprint = make_google_blueprint(
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    scope=["profile", "email"],
    redirect_url="/google_login"
)
app.register_blueprint(blueprint, url_prefix="/login")

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

# --- Groq AI Engine ---
def RealtimeEngine(prompt):
    if any(op in prompt for op in ["+","-","*","/","=","solve","integrate","derivative","diff","factor","limit"]):
        return solve_math(prompt)
    if "who is your developer" in prompt.lower():
        return f"My developer is {DeveloperName}. {FullInformation}"
    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role":"system","content":f"You are {AssistantName}, an AI built by {DeveloperName}. Follow prompt: talkative, witty, professional, Gen Z style."},
                {"role":"user","content":prompt}
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
    if 'user' in session:
        return redirect(url_for("chat_page"))
    return render_template("index.html", user=None, assistant_name=AssistantName)

@app.route("/google_login")
def google_login():
    if not google.authorized:
        return redirect(url_for("google.login"))
    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return redirect(url_for("home"))
    session['user'] = resp.json()
    return redirect(url_for("chat_page"))

@app.route("/chat_page")
def chat_page():
    if 'user' not in session:
        return redirect(url_for("home"))
    return render_template("index.html", user=session['user'], assistant_name=AssistantName)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_prompt = data.get("message","")
    if not user_prompt:
        return jsonify({"reply":"Please enter a message."}),400

    reply = RealtimeEngine(user_prompt)

    # Save chat log
    try:
        os.makedirs("chats", exist_ok=True)
        user_file = f"chats/{session['user']['email'] if 'user' in session else 'guest'}.json"
        chat_log = {"user":user_prompt,"assistant":reply}
        if os.path.exists(user_file):
            existing = json.load(open(user_file,"r"))
            existing.append(chat_log)
            json.dump(existing, open(user_file,"w"), indent=2)
        else:
            json.dump([chat_log], open(user_file,"w"), indent=2)
    except Exception as e:
        print("Error saving chat:", e)

    return jsonify({"reply":reply})

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))

if __name__=="__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port, debug=True)
