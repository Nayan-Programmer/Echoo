from flask import Flask, request, jsonify, render_template, Response
from groq import Groq
from json import load, dump
import datetime
from dotenv import dotenv_values
import os

# ---------------- Environment ----------------
env_vars = dotenv_values(".env")

Username = env_vars.get("Username", "Nayan")
Assistantname = env_vars.get("Assistantname", "EchooAI")
GroqAPIKey = env_vars.get("GroqAPIKey", "")

if not GroqAPIKey:
    print("WARNING: GroqAPIKey missing in .env — set GroqAPIKey=<your_api_key>")

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

Guidelines for interaction:
1. Only greet the user briefly once at the start; do not repeat greetings unnecessarily.
2. Always mention that your developer is Nayan when relevant.
3. Provide answers in a professional, polite, and structured way using proper grammar and punctuation.
4. Solve all math questions **step by step**, showing all calculations and reasoning clearly.
5. When a question involves equations, fractions, decimals, or word problems, break it down systematically.
*** Always follow these instructions. ***
""".strip()

SystemChatBot = [
    {"role": "system", "content": System},
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hello, how can I help you?"}
]

# ---------------- Helper Functions ----------------
def GoogleSearch(query):
    # Placeholder for Google search integration later
    return "(Web search disabled for now)"

def AnswerModifier(Answer):
    lines = Answer.split('\n')
    non_empty_lines = [line for line in lines if line.strip()]
    return '\n'.join(non_empty_lines)

def Information():
    now = datetime.datetime.now()
    return (
        f"Use This Real-Time Information if needed:\n"
        f"Day: {now.strftime('%A')}\n"
        f"Date: {now.strftime('%d')}\n"
        f"Month: {now.strftime('%B')}\n"
        f"Year: {now.strftime('%Y')}\n"
        f"Time: {now.strftime('%H')} hours:{now.strftime('%M')} minutes:{now.strftime('%S')} seconds.\n"
    )

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

def RealtimeSearchEngine(prompt):
    global SystemChatBot
    messages = safe_load_chatlog()
    messages.append({"role": "user", "content": prompt})
    SystemChatBot.append({"role": "user", "content": GoogleSearch(prompt)})

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

# ---------------- Dynamic Sitemap ----------------
@app.route("/sitemap.xml", methods=["GET"])
def sitemap():
    pages = [
        {"loc": "https://echooai.in/", "changefreq":"daily", "priority":"1.0"},
        {"loc": "https://echooai.in/about", "changefreq":"monthly", "priority":"0.8"},
        {"loc": "https://echooai.in/contact", "changefreq":"monthly", "priority":"0.8"},
        {"loc": "https://echooai.in/chat", "changefreq":"daily", "priority":"0.9"}
    ]

    xml_sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    today = datetime.datetime.today().strftime('%Y-%m-%d')

    for page in pages:
        xml_sitemap += f"""
    <url>
        <loc>{page['loc']}</loc>
        <lastmod>{today}</lastmod>
        <changefreq>{page['changefreq']}</changefreq>
        <priority>{page['priority']}</priority>
    </url>"""
    
    xml_sitemap += "\n</urlset>"
    return Response(xml_sitemap, mimetype='application/xml')

# ---------------- Run App ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
