from flask import Flask, render_template, redirect, url_for, session, request, jsonify
from flask_dance.contrib.google import make_google_blueprint, google
from sympy import sympify, simplify, solve, pretty
from dotenv import dotenv_values
from groq import Groq
import os, json

# Load env
env = dotenv_values(".env")
AssistantName = env.get("AssistantName","EchooAI")
DeveloperName = env.get("DeveloperName","Nayan")
FullInformation = env.get("FullInformation","")
GroqAPIKey = env.get("GroqAPIKey","")

client = Groq(api_key=GroqAPIKey)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.urandom(24)

# --- Google OAuth ---
google_bp = make_google_blueprint(
    client_id=env.get("GOOGLE_CLIENT_ID"),
    client_secret=env.get("GOOGLE_CLIENT_SECRET"),
    scope=["profile", "email"],
    redirect_url="/login/google/authorized"
)
app.register_blueprint(google_bp, url_prefix="/login")

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

# --- AI Engine ---
def RealtimeEngine(prompt):
    if any(op in prompt for op in ["+","-","*","/","=","solve","integrate","derivative","diff","factor","limit"]):
        return solve_math(prompt)
    if "who is your developer" in prompt.lower():
        return f"My developer is {DeveloperName}. {FullInformation}"
    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role":"system","content":f"You are {AssistantName}, an AI built by {DeveloperName}. Talkative, witty, professional, Gen Z style."},
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
    if not google.authorized:
        return redirect(url_for("google.login"))
    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return redirect(url_for("google.login"))
    user_info = resp.json()
    session["user"] = user_info
    return render_template("index.html", assistant_name=AssistantName, user_name=user_info.get("name"))

@app.route("/chat", methods=["POST"])
def chat():
    if "user" not in session:
        return jsonify({"reply":"Please log in first."}),401
    data = request.get_json()
    user_prompt = data.get("message","")
    if not user_prompt:
        return jsonify({"reply":"Please enter a message."}),400

    reply = RealtimeEngine(user_prompt)

    # Save chat log
    try:
        os.makedirs("chats", exist_ok=True)
        filename = f"chats/{session['user']['email']}.json"
        chat_log = {"user":user_prompt,"assistant":reply}
        if os.path.exists(filename):
            existing = json.load(open(filename,"r"))
            existing.append(chat_log)
            json.dump(existing, open(filename,"w"), indent=2)
        else:
            json.dump([chat_log], open(filename,"w"), indent=2)
    except Exception as e:
        print("Error saving chat:", e)

    return jsonify({"reply":reply})

if __name__=="__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port, debug=True)
