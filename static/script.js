// Function to handle sending the message (AJAX Logic)
async function sendMessage() {
    const chatWindow = document.getElementById('chat-window');
    const userInput = document.getElementById('user-input');
    const chatIDInput = document.getElementById('current-chat-id');
    const sidebarHistory = document.getElementById('sidebar-history');
    
    const message = userInput.value.trim();

    if (message === "") return;

    // 1. Display user message
    appendMessage(message, 'user');

    // 2. Clear input
    userInput.value = '';

    // 3. Display loading message
    const typingIndicator = appendMessage("Typing...", 'loading-indicator');
    
    try {
        // 4. Send to Flask backend
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                message: message,
                chat_id: chatIDInput.value
            }) 
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // 5. Remove loading message
        typingIndicator.remove(); 

        // 6. Display AI response
        appendMessage(data.response, 'bot');
        
        // 7. Dynamic Sidebar Update 
        if (data.title_updated) {
            const oldItem = document.getElementById(`history-${data.chat_id}`);
            if (oldItem) {
                oldItem.remove();
            }
            sidebarHistory.insertAdjacentHTML('afterbegin', data.new_history_html);
            chatIDInput.value = data.chat_id;
        } 
        
        // Re-apply active class
        document.querySelectorAll('.history-item').forEach(item => {
            item.classList.remove('active-chat');
        });
        const currentHistoryItem = document.getElementById(`history-${data.chat_id}`);
        if (currentHistoryItem) {
            currentHistoryItem.classList.add('active-chat');
        }


    } catch (error) {
        console.error('Fetch Error:', error);
        typingIndicator.remove();
        appendMessage("Sorry, the connection failed. Please check the terminal for errors.", "bot error");
    }
}

// Function to add a new message div to the chat window
function appendMessage(message, sender) {
    const chatWindow = document.getElementById('chat-window');
    const messageDiv = document.createElement("div");
    
    messageDiv.classList.add("message");
    if (sender === 'loading-indicator') {
        messageDiv.classList.add('loading-indicator');
    } else {
        messageDiv.classList.add(`${sender}-message`);
    }
    
    messageDiv.innerHTML = message; 
    
    chatWindow.appendChild(messageDiv);
    chatWindow.scrollTop = chatWindow.scrollHeight;

    return messageDiv; 
}


// === DARK MODE LOGIC ===

function toggleTheme() {
    const isDark = document.body.classList.toggle('dark-theme');
    const toggleButton = document.getElementById('theme-toggle');

    if (isDark) {
        localStorage.setItem('theme', 'dark');
        toggleButton.innerHTML = '🌙'; 
    } else {
        localStorage.setItem('theme', 'light');
        toggleButton.innerHTML = '☀️'; 
    }
}

// Event listener to apply saved theme on load and attach toggle function
document.addEventListener('DOMContentLoaded', () => {
    // 1. Apply saved theme
    const savedTheme = localStorage.getItem('theme');
    const toggleButton = document.getElementById('theme-toggle');

    if (savedTheme === 'dark') {
        document.body.classList.add('dark-theme');
        if (toggleButton) toggleButton.innerHTML = '🌙';
    } else {
        if (toggleButton) toggleButton.innerHTML = '☀️';
    }

    // 2. Attach toggle function to button
    if (toggleButton) {
        toggleButton.addEventListener('click', toggleTheme);
    }
});