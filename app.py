from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import requests, os
from dotenv import dotenv_values

# Load environment variables
env = dotenv_values(".env")
AssistantName = env.get("AssistantName", "EchooAI")
DeveloperName = env.get("DeveloperName", "Nayan")
StabilityKey = env.get("STABILITY_API_KEY", "")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.urandom(24)

# --- Simple AI Chat engine ---
def chat_engine(prompt):
    # For now, simple echo or canned responses
    if "who created you" in prompt.lower() or "developer" in prompt.lower():
        return f"My developer is {DeveloperName}. I am a chatbot AI."
    # Add simple chatter
    return f"You said: {prompt}"

# --- Image Generation ---
@app.route("/image-gen", methods=["POST"])
def image_gen():
    user_info = session.get('user_info', {'name':'User'})
    data = request.get_json()
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "Prompt is required."}), 400

    try:
        headers = {"Authorization": f"Bearer {StabilityKey}"}
        payload = {
            "text_prompts": [{"text": prompt}],
            "cfg_scale": 7,
            "steps": 30,
            "samples": 1,
            "width": 512,
            "height": 512,
            "output_format": "webp"
        }

        response = requests.post(
            "https://api.stability.ai/v2beta/stable-image/generate",
            headers=headers,
            json=payload
        )

        resp_json = response.json()
        if response.status_code == 200 and "artifacts" in resp_json:
            images = []
            for artifact in resp_json["artifacts"]:
                img_base64 = artifact.get("base64")
                if img_base64:
                    images.append("data:image/webp;base64," + img_base64)
            return jsonify({"images": images})

        return jsonify({"error": "Stability API failed", "details": resp_json}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Routes ---
@app.route("/")
def home():
    if 'chat_sessions' not in session:
        session['chat_sessions'] = []
        session['active_chat'] = None
    return render_template("index.html",
                           chat_sessions=session['chat_sessions'],
                           active_chat=session['active_chat'],
                           user_info={'name':'User'})

@app.route("/chat", methods=["POST"])
def chat():
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

    active_chat = session['active_chat']
    for chat_item in session['chat_sessions']:
        if chat_item['id'] == active_chat:
            chat_item['messages'].append({"sender": "user", "message": user_prompt})
            reply = chat_engine(user_prompt)
            chat_item['messages'].append({"sender": "ai", "message": reply})
            session.modified = True
            return jsonify({"reply": reply})

    return jsonify({"reply": "Error: Active chat not found."}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

