from flask import Flask, request, jsonify, render_template
from groq import Groq
from json import load, dump
from dotenv import dotenv_values
import os, datetime, requests

# ---------------- Environment ----------------
env = dotenv_values(".env")
Username = env.get("Username", "Nayan")
Assistantname = env.get("Assistantname", "EchooAI")
GroqAPIKey = env.get("GroqAPIKey", "")
GoogleCSEID = env.get("GoogleCSEID", "")
GoogleAPIKey = env.get("GoogleAPIKey", "")

client = Groq(api_key=GroqAPIKey) if GroqAPIKey else None

# ---------------- Flask ----------------
app = Flask(__name__, template_folder="templates")

os.makedirs("Data", exist_ok=True)
chatlog_path = os.path.join("Data", "ChatLog.json")
if not os.path.exists(chatlog_path):
    with open(chatlog_path,"w",encoding="utf-8") as f: dump([], f, indent=4)

# ---------------- System ----------------
System = f"""
Hello, I am {Username}, your developer.
You are {Assistantname}, a highly advanced AI chatbot.
Solve all math questions step by step.
Always mention your developer when relevant.
"""

SystemChatBot = [
    {"role":"system","content":System},
    {"role":"user","content":"Hi"},
    {"role":"assistant","content":"Hello, how can I help you?"}
]

# ---------------- Helpers ----------------
def GoogleSearch(query):
    if not GoogleAPIKey or not GoogleCSEID:
        return "(Google Search not configured)"
    url = f"https://www.googleapis.com/customsearch/v1?key={GoogleAPIKey}&cx={GoogleCSEID}&q={query}"
    try:
        res = requests.get(url).json()
        items = res.get("items", [])
        return "\n".join([f"{i+1}. {item['title']}: {item['link']}" for i,item in enumerate(items[:5])])
    except:
        return "(Error fetching search results)"

def safe_load_chatlog():
    try:
        with open(chatlog_path,"r") as f: return load(f)
    except: return []

def safe_write_chatlog(messages):
    try:
        with open(chatlog_path,"w") as f: dump(messages,f,indent=4)
    except: pass

def RealtimeSearchEngine(prompt):
    global SystemChatBot
    messages = safe_load_chatlog()
    messages.append({"role":"user","content":prompt})
    # Append Google search results
    SystemChatBot.append({"role":"user","content":GoogleSearch(prompt)})

    try:
        completion = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=SystemChatBot + messages,
            max_tokens=2048,
            temperature=0.7,
            top_p=1,
            stream=True
        )
        Answer = ""
        for chunk in completion:
            if chunk.choices[0].delta.content:
                Answer += chunk.choices[0].delta.content
        Answer = Answer.strip().replace("</s>","")
    except Exception as e:
        Answer = f"AI backend error: {e}"

    messages.append({"role":"assistant","content":Answer})
    safe_write_chatlog(messages)
    SystemChatBot.pop()
    return Answer

# ---------------- Routes ----------------
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html", assistant_name=Assistantname)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_prompt = data.get("message","")
    if not user_prompt: return jsonify({"reply":"Please enter a message."}), 400
    reply = RealtimeSearchEngine(user_prompt)
    return jsonify({"reply":reply})

if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port, debug=True)
