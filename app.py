from flask import Flask, request, jsonify, render_template
from sympy import sympify, solve, simplify, pretty
from dotenv import dotenv_values
from groq import Groq
import requests, os

# ---------------- Load ENV ----------------
env = dotenv_values(".env")
Username = env.get("Username", "Nayan")
AssistantName = env.get("AssistantName", "EchooAI")
GroqAPIKey = env.get("GroqAPIKey", "")
GoogleAPIKey = env.get("GoogleAPIKey", "")
GoogleCSEID = env.get("GoogleCSEID", "")

client = Groq(api_key=GroqAPIKey)
app = Flask(__name__, template_folder="templates")

# ---------------- Math Solver ----------------
def solve_math(query):
    try:
        expr = sympify(query)
        simplified = simplify(expr)
        solution = solve(expr)
        return (
            f"Step 1: Expression received → {pretty(expr)}\n"
            f"Step 2: Simplified → {pretty(simplified)}\n"
            f"Step 3: Solution → {solution if solution else 'No closed form solution'}"
        )
    except Exception as e:
        return f"Math Error: {e}"

# ---------------- Google Search ----------------
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

# ---------------- AI Engine ----------------
def RealtimeEngine(prompt):
    # 1. Math detection
    if any(op in prompt for op in ["+", "-", "*", "/", "=", "solve", "integrate", "derivative"]):
        return solve_math(prompt)

    # 2. Google search detection
    if prompt.lower().startswith("search:"):
        query = prompt.replace("search:", "").strip()
        return GoogleSearch(query)

    # 3. Groq LLM (default)
    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",   # ✅ Groq ka sabse powerful model
            messages=[
                {"role": "system", "content": f"You are {AssistantName}, an AI built by {Username}. Always respond politely and clearly."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Groq backend error: {e}"

# ---------------- Routes ----------------
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html", assistant_name=AssistantName)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_prompt = data.get("message", "")
    if not user_prompt:
        return jsonify({"reply": "Please enter a message."}), 400
    reply = RealtimeEngine(user_prompt)
    return jsonify({"reply": reply})

# ---------------- Run ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
