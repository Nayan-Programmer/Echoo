from flask import Flask, request, jsonify, render_template
from groq import Groq
from json import load, dump
import datetime, requests, os
from dotenv import dotenv_values

# ---------------- Environment ----------------
env_vars = dotenv_values(".env")

Username = env_vars.get("Username", "Nayan")
Assistantname = env_vars.get("Assistantname", "EchooAI")
GroqAPIKey = env_vars.get("GroqAPIKey", "")
GOOGLE_API_KEY = env_vars.get("GOOGLE_API_KEY", "")
GOOGLE_CX = env_vars.get("GOOGLE_CX", "")

if not GroqAPIKey:
    print("WARNING: GroqAPIKey missing in .env")
if not GOOGLE_API_KEY or not GOOGLE_CX:
    print("WARNING: Google API Key or CX missing in .env")

client = Groq(api_key=GroqAPIKey) if GroqAPIKey else None

# ---------------- Flask ----------------
app = Flask(__name__, template_folder="templates")

# Ensure Data folder and ChatLog.json exist
os.makedirs("Data", exist_ok=True)
chatlog_path = os.path.join("Data", "ChatLog.json")
if not os.path.exists(chatlog_path):
    with open(chatlog_path, "w", encoding="utf-8") as f:
        dump([], f, indent=4)

# ---------------- System Prompt ----------------
System = f"""
Hello, I am {Username}. I am a brilliant student studying in 6th class at A.B.B.S School. My name is Nayan. I am your developer 

You are a highly advanced AI chatbot named {Assistantname}, capable of real-time, up-to-date information retrieval from the internet.

Guidelines:
1. Only greet the user briefly once.
2. Always mention that your developer is Nayan when relevant.
3. Provide answers in professional, structured way.
4. Solve all math questions step by step.
5. When a question involves equations, fractions, decimals, or word problems, break it down systematically.
*** Always follow these instructions. ***
""".strip()

SystemChatBot = [
    {"role": "system", "content": System},
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hello, how can I help you?"}
]

# ---------------- Helper Functions ----------------
def safe_load_chatlog():
    try:
        with open(chatlog_path, "r") as f:
            return load(f)
    except:
        return []

def safe_write_chatlog(messages):
    try:
        with open(chatlog_path, "w") as f:
            dump(messages, f, indent=4)
    except Exception as e:
        print("Failed to write chat log:", e)

def Information():
    now = datetime.datetime.now()
    return (
        f"Use This Real-Time Info if needed:\n"
        f"Day: {now.strftime('%A')}\n"
        f"Date: {now.strftime('%d')}\n"
        f"Month: {now.strftime('%B')}\n"
        f"Year: {now.strftime('%Y')}\n"
        f"Time: {now.strftime('%H')}h:{now.strftime('%M')}m:{now.strftime('%S')}s\n"
    )

# ---------------- Google Search ----------------
def GoogleSearch(query):
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {"key": GOOGLE_API_KEY, "cx": GOOGLE_CX, "q": query, "num": 3}
        response = requests.get(url, params=params)
        data = response.json()
        results = []
        for item in data.get("items", []):
            title = item.get("title")
            link = item.get("link")
            snippet = item.get("snippet")
            results.append(f"{title}\n{snippet}\n{link}")
        return "\n\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Google search error: {e}"

def AnswerModifier(Answer):
    lines = Answer.split('\n')
    non_empty_lines = [line for line in lines if line.strip()]
    return '\n'.join(non_empty_lines)

# ---------------- AI + Search Engine ----------------
def RealtimeSearchEngine(prompt):
    global SystemChatBot
    messages = safe_load_chatlog()
    messages.append({"role": "user", "content": prompt})

    # Google Search result
    search_result = GoogleSearch(prompt)
    SystemChatBot.append({"role": "user", "content": search_result})

    try:
        completion = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=SystemChatBot + [{"role": "system", "content": Information()}] + messages,
            max_tokens=2048,
            temperature=0.7,
            top_p=1,
            stream=True,
            stop=None,
        )
        Answer = ""
        for chunk in completion:
            if chunk.choices[0].delta.content:
                Answer += chunk.choices[0].delta.content
        Answer = Answer.strip().replace("</s>", "")
    except Exception as e:
        Answer = f"AI backend error: {e}"

    messages.append({"role": "assistant", "content": Answer})
    safe_write_chatlog(messages)
    SystemChatBot.pop()
    return AnswerModifier(Answer)

# ---------------- Flask Routes ----------------
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html", assistant_name=Assistantname)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_prompt = data.get("message", "")
    if not user_prompt:
        return jsonify({"reply": "Please enter a message."}), 400
    reply = RealtimeSearchEngine(user_prompt)
    return jsonify({"reply": reply})

# ---------------- Run App ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
