// Global variables
let messages = [];
let isTyping = false;

// DOM elements
const welcomeScreen = document.getElementById('welcomeScreen');
const chatArea = document.getElementById('chatArea');
const messageInputContainer = document.getElementById('messageInputContainer');
const messagesContainer = document.getElementById('messagesContainer');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const startChatBtn = document.getElementById('startChatBtn');
const clearChatBtn = document.getElementById('clearChat');
const typingIndicator = document.getElementById('typingIndicator');

// AI Response templates (simulating your original Flask responses)
const aiResponses = {
    greetings: [
        "Hello! I'm Echooai, your premium AI assistant. How can I help you today?",
        "Hi there! I'm ready to assist you with any questions or tasks. What would you like to explore?",
        "Welcome! I'm Echooai, and I'm here to help you solve problems, answer questions, and get creative. What can I do for you?",
        "Great to meet you! I'm your AI assistant Echooai. I can help with math, research, creative tasks, and much more. What interests you?"
    ],
    
    general: [
        "That's an interesting question! Let me help you with that.",
        "I'd be happy to assist you with this. Here's what I think...",
        "Great question! Based on what you've asked, I can provide some insights.",
        "Thank you for reaching out! Here's how I can help you with that.",
        "That's a thoughtful inquiry. Let me break this down for you.",
        "I understand what you're asking. Here's my perspective on this...",
        "Let me analyze this for you and provide a comprehensive response.",
        "Excellent question! This is something I can definitely help you explore."
    ],
    
    math: [
        "Let me solve this mathematical problem for you step by step.",
        "I'll work through this calculation and show you the solution.",
        "Here's how I would approach this math problem:",
        "Let me break down this equation for you:"
    ],
    
    creative: [
        "I love creative challenges! Here are some ideas for you:",
        "Let's get creative! I have several suggestions:",
        "Creative thinking is my specialty. Here's what I came up with:",
        "Time to unleash some creativity! Here are my thoughts:"
    ],
    
    research: [
        "Based on my knowledge, here's what I can tell you about this topic:",
        "Let me share some insights about this subject:",
        "Here's what I know about this area:",
        "I'll provide you with comprehensive information on this topic:"
    ]
};

// Simple math solver (basic operations)
function solveMath(expression) {
    try {
        // Clean the expression
        const cleanExpr = expression.replace(/[^0-9+\-*/.() ]/g, '');
        
        // Basic safety check - only allow numbers and basic operators
        if (!/^[0-9+\-*/.() ]+$/.test(cleanExpr)) {
            return "I can help with basic arithmetic. Try something like: 2 + 2, 10 * 5, or (15 - 3) / 4";
        }
        
        // Evaluate the expression
        const result = Function('"use strict"; return (' + cleanExpr + ')')();
        
        return `Step 1: Expression received → ${expression}
Step 2: Calculation → ${cleanExpr}
Step 3: Result → ${result}

The answer is: ${result}`;
    } catch (error) {
        return "I couldn't solve that math problem. Please try a simpler expression like: 2 + 2, 10 * 5, or (15 - 3) / 4";
    }
}

// Detect content type and generate appropriate response
function generateAIResponse(userMessage) {
    const message = userMessage.toLowerCase();
    
    // Math detection
    if (message.match(/[\+\-\*\/\(\)=]/) || 
        message.includes('solve') || 
        message.includes('calculate') ||
        message.includes('math') ||
        /^\d+[\+\-\*\/]\d+/.test(message)) {
        const mathResponse = solveMath(userMessage);
        return `${getRandomResponse(aiResponses.math)}\n\n${mathResponse}`;
    }
    
    // Search detection
    if (message.startsWith('search:') || message.includes('search for') || message.includes('find information')) {
        const searchTerm = message.replace('search:', '').trim();
        return `${getRandomResponse(aiResponses.research)}\n\nI don't have real-time search capabilities in this demo, but I can help you think through topics related to "${searchTerm}". For actual web searches, you might want to try using search engines like Google or academic databases for research topics.`;
    }
    
    // Creative tasks detection
    if (message.includes('creative') || 
        message.includes('idea') || 
        message.includes('brainstorm') ||
        message.includes('design') ||
        message.includes('write') ||
        message.includes('story') ||
        message.includes('poem')) {
        const creativeIdeas = [
            "• Start with a mind map to explore all angles",
            "• Look for unexpected connections between different concepts", 
            "• Try the 'what if' approach - ask what if scenarios",
            "• Break down big ideas into smaller, manageable pieces",
            "• Draw inspiration from other fields or industries",
            "• Use storytelling to make your ideas more engaging"
        ];
        return `${getRandomResponse(aiResponses.creative)}\n\n${creativeIdeas.join('\n')}`;
    }
    
    // Greeting detection
    if (message.includes('hello') || 
        message.includes('hi') || 
        message.includes('hey') ||
        message === 'start' ||
        message.length < 10) {
        return getRandomResponse(aiResponses.greetings);
    }
    
    // Default general response
    return getRandomResponse(aiResponses.general);
}

// Get random response from array
function getRandomResponse(responseArray) {
    return responseArray[Math.floor(Math.random() * responseArray.length)];
}

// Format timestamp
function formatTime(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Create message element
function createMessageElement(message, isUser = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user' : 'ai'}`;
    messageDiv.setAttribute('data-testid', `message-${isUser ? 'user' : 'ai'}-${message.id}`);
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    
    const avatar = document.createElement('div');
    avatar.className = `message-avatar ${isUser ? 'user-avatar' : 'ai-avatar'}`;
    
    if (isUser) {
        avatar.textContent = 'U';
    } else {
        avatar.innerHTML = `
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
        `;
    }
    
    const bubbleContainer = document.createElement('div');
    
    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${isUser ? 'user' : 'ai'}`;
    
    const text = document.createElement('div');
    text.className = 'message-text';
    text.textContent = message.content;
    
    const time = document.createElement('span');
    time.className = 'message-time';
    time.textContent = formatTime(message.timestamp);
    
    bubble.appendChild(text);
    bubbleContainer.appendChild(bubble);
    bubbleContainer.appendChild(time);
    
    messageContent.appendChild(avatar);
    messageContent.appendChild(bubbleContainer);
    messageDiv.appendChild(messageContent);
    
    return messageDiv;
}

// Add message to chat
function addMessage(content, isUser = false) {
    const message = {
        id: Date.now() + Math.random(),
        content: content,
        isAI: !isUser,
        timestamp: new Date()
    };
    
    messages.push(message);
    
    const messageElement = createMessageElement(message, isUser);
    messagesContainer.appendChild(messageElement);
    
    // Scroll to bottom
    messageElement.scrollIntoView({ behavior: 'smooth' });
    
    return message;
}

// Show typing indicator
function showTypingIndicator() {
    isTyping = true;
    typingIndicator.style.display = 'flex';
    typingIndicator.scrollIntoView({ behavior: 'smooth' });
}

// Hide typing indicator
function hideTypingIndicator() {
    isTyping = false;
    typingIndicator.style.display = 'none';
}

// Send message
async function sendMessage() {
    const content = messageInput.value.trim();
    if (!content || isTyping) return;
    
    // Add user message
    addMessage(content, true);
    
    // Clear input
    messageInput.value = '';
    resizeTextarea();
    updateSendButton();
    
    // Show typing indicator
    showTypingIndicator();
    
    // Simulate AI thinking time (1-3 seconds)
    const thinkingTime = 1000 + Math.random() * 2000;
    
    setTimeout(() => {
        hideTypingIndicator();
        
        // Generate and add AI response
        const aiResponse = generateAIResponse(content);
        addMessage(aiResponse, false);
    }, thinkingTime);
}

// Start chat
function startChat() {
    welcomeScreen.style.display = 'none';
    chatArea.style.display = 'flex';
    messageInputContainer.style.display = 'block';
    
    // Add welcome message
    setTimeout(() => {
        const welcomeMsg = "Hello! I'm Echooai, your premium AI assistant. I'm here to help you with any questions, creative projects, or problem-solving tasks. What would you like to explore today?";
        addMessage(welcomeMsg, false);
    }, 500);
    
    // Focus on input
    messageInput.focus();
}

// Clear chat
function clearChat() {
    messages = [];
    messagesContainer.innerHTML = '';
    welcomeScreen.style.display = 'flex';
    chatArea.style.display = 'none';
    messageInputContainer.style.display = 'none';
    hideTypingIndicator();
}

// Auto-resize textarea
function resizeTextarea() {
    messageInput.style.height = 'auto';
    const newHeight = Math.min(messageInput.scrollHeight, 128);
    messageInput.style.height = newHeight + 'px';
}

// Update send button state
function updateSendButton() {
    const hasContent = messageInput.value.trim().length > 0;
    sendBtn.disabled = !hasContent || isTyping;
}

// Handle keyboard events
function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

// Set quick action
function setQuickAction(text) {
    messageInput.value = text;
    resizeTextarea();
    updateSendButton();
    messageInput.focus();
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Start chat button
    startChatBtn.addEventListener('click', startChat);
    
    // Clear chat button
    clearChatBtn.addEventListener('click', clearChat);
    
    // Send button
    sendBtn.addEventListener('click', sendMessage);
    
    // Message input
    messageInput.addEventListener('input', function() {
        resizeTextarea();
        updateSendButton();
    });
    
    messageInput.addEventListener('keydown', handleKeyDown);
    
    // Quick start cards
    document.querySelectorAll('.quick-start-card').forEach(card => {
        card.addEventListener('click', startChat);
    });
    
    // Quick action buttons
    document.querySelectorAll('.quick-action-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            setQuickAction(this.textContent);
        });
    });
    
    // Initialize send button state
    updateSendButton();
    
    // Add some demo messages for development
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        console.log('Echooai Chat Bot initialized successfully!');
        console.log('Features available:');
        console.log('- Basic math solving (try: 2 + 2 * 5)');
        console.log('- Creative assistance (try: help me with creative ideas)');
        console.log('- General Q&A (try: hello or ask any question)');
        console.log('- Search simulation (try: search: artificial intelligence)');
    }
});

// Add some utility functions for demo purposes
window.echooai = {
    // Simulate the original Flask functions
    solveMath: solveMath,
    generateResponse: generateAIResponse,
    addMessage: addMessage,
    startChat: startChat,
    clearChat: clearChat
};

// Handle page visibility change to pause/resume
document.addEventListener('visibilitychange', function() {
    if (document.hidden && isTyping) {
        // Pause typing indicator when page is hidden
        console.log('Page hidden, maintaining typing state');
    } else if (!document.hidden && isTyping) {
        // Resume typing indicator when page is visible
        console.log('Page visible, continuing typing indication');
    }
});

// Prevent form submission on Enter key
document.addEventListener('keydown', function(e) {
    if (e.target === messageInput && e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
    }
});
