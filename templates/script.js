// Grab all necessary DOM elements
const welcomeScreen = document.getElementById('welcomeScreen');
const chatArea = document.getElementById('chatArea');
const messageInputContainer = document.getElementById('messageInputContainer');
const messagesContainer = document.getElementById('messagesContainer');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const startChatBtn = document.getElementById('startChatBtn');
const clearChatBtn = document.getElementById('clearChat');
const typingIndicator = document.getElementById('typingIndicator');

let isTyping = false;

// Show a message in the chat
function createMessageElement(content, isUser = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user' : 'ai'}`;

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.textContent = content;

    const time = document.createElement('span');
    time.className = 'message-time';
    const now = new Date();
    time.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    bubble.appendChild(time);
    messageDiv.appendChild(bubble);
    messagesContainer.appendChild(messageDiv);
    messageDiv.scrollIntoView({ behavior: 'smooth' });
}

// Show typing indicator
function showTyping() {
    typingIndicator.style.display = 'flex';
}

// Hide typing indicator
function hideTyping() {
    typingIndicator.style.display = 'none';
}

// Send user message to Flask backend
async function sendMessage() {
    const content = messageInput.value.trim();
    if (!content || isTyping) return;

    createMessageElement(content, true);
    messageInput.value = '';
    updateSendButton();

    showTyping();
    isTyping = true;

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: content })
        });

        const data = await response.json();
        hideTyping();
        isTyping = false;

        createMessageElement(data.reply, false);
    } catch (err) {
        hideTyping();
        isTyping = false;
        createMessageElement("Error connecting to server.", false);
    }
}

// Start chat button
function startChat() {
    welcomeScreen.style.display = 'none';
    chatArea.style.display = 'block';
    messageInputContainer.style.display = 'block';
}

// Clear chat
function clearChat() {
    messagesContainer.innerHTML = '';
    welcomeScreen.style.display = 'block';
    chatArea.style.display = 'none';
    messageInputContainer.style.display = 'none';
}

// Enable/disable send button based on input
function updateSendButton() {
    sendBtn.disabled = !messageInput.value.trim() || isTyping;
}

// Event listeners
startChatBtn.addEventListener('click', startChat);
sendBtn.addEventListener('click', sendMessage);
clearChatBtn.addEventListener('click', clearChat);

messageInput.addEventListener('input', updateSendButton);
messageInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Optional: Add quick-action buttons if you want them to prefill messages
document.querySelectorAll('.quick-action-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        messageInput.value = btn.textContent;
        updateSendButton();
        messageInput.focus();
    });
});
