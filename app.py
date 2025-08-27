from flask import Flask, request, jsonify, render_template
from sympy import sympify, solve, simplify, pretty
from dotenv import dotenv_values
from groq import Groq
import requests, os, json

# Load env
env = dotenv_values(".env")
AssistantName = env.get("AssistantName","EchooAI")
GroqAPIKey = env.get("GroqAPIKey","")
GoogleAPIKey = env.get("GoogleAPIKey","")
GoogleCSEID = env.get("GoogleCSEID","")
DeveloperName = env.get("DeveloperName","Nayan")
FullInformation = env.get("FullInformation","")

# Initialize Groq client
client = Groq(api_key=GroqAPIKey)
app = Flask(__name__, template_folder="templates", static_folder="static")

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
    if any(op in prompt for op in ["+", "-", "*", "/", "=", "solve", "integrate", "derivative", "diff", "factor", "limit"]):
        return solve_math(prompt)
    if prompt.lower().startswith("search:"):
        query = prompt.replace("search:","").strip()
        return GoogleSearch(query)
    if "who is your developer" in prompt.lower() or "who created you" in prompt.lower():
        return f"My developer is {DeveloperName}. {FullInformation}"
    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role":"system","content":f"You are {AssistantName}, an AI built by {DeveloperName}."},
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
    return render_template("index.html", assistant_name=AssistantName)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_prompt = data.get("message","")
    user_name = data.get("user_name","Guest")
    user_email = data.get("user_email","guest@example.com")
    if not user_prompt:
        return jsonify({"reply":"Please enter a message."}),400

    reply = RealtimeEngine(user_prompt)

    # Optional: Save chat to file per user
    try:
        filename = f"chats/{user_email.replace('@','_at_')}.json"
        os.makedirs("chats", exist_ok=True)
        chat_log = {"user":user_prompt, "assistant":reply}
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
