/**
 * Enhanced Frontend Logic for HealthGuru Chat App
 * - Handles Dark Theme Toggle (for future light theme)
 * - Handles Sidebar Open/Close on Mobile
 * - Handles Chat Form Submission and Display
 */
document.addEventListener('DOMContentLoaded', function() {
    
    // --- DOM Elements ---
    const body = document.body;
    const sidebar = document.getElementById('sidebar');
    const openSidebarBtn = document.getElementById('open-sidebar-btn');
    const closeSidebarBtn = document.getElementById('close-sidebar-btn');
    const themeToggle = document.getElementById('theme-toggle');
    
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message-input');
    const chatBox = document.getElementById('chat-box');
    const chatIDElement = document.getElementById('chat-id');
    const THEME_KEY = 'theme';


    // --- 1. Sidebar Toggle Logic (For Mobile View) ---
    if (openSidebarBtn && closeSidebarBtn && sidebar) {
        openSidebarBtn.addEventListener('click', () => {
            sidebar.classList.add('open');
            // Hide main content overflow when sidebar is open
            body.style.overflow = 'hidden'; 
            // Also update input area width
            updateInputAreaWidth();
        });

        closeSidebarBtn.addEventListener('click', () => {
            sidebar.classList.remove('open');
            body.style.overflow = '';
            // Also update input area width
            updateInputAreaWidth();
        });
        
        // Close sidebar if window resized to desktop size
        window.addEventListener('resize', () => {
            if (window.innerWidth > 768) {
                sidebar.classList.remove('open');
                body.style.overflow = '';
            }
            updateInputAreaWidth();
        });
    }

    // Function to update the width of the fixed input area
    function updateInputAreaWidth() {
        const inputArea = document.getElementById('input-area');
        if (sidebar && inputArea) {
             const sidebarIsVisible = window.innerWidth > 768 || sidebar.classList.contains('open');
            
            if (sidebarIsVisible) {
                // Set fixed width and position based on sidebar size
                inputArea.style.width = `calc(100% - ${sidebar.offsetWidth}px)`;
                inputArea.style.left = `${sidebar.offsetWidth}px`;
            } else {
                 // Full width on mobile when sidebar is closed
                 inputArea.style.width = '100%';
                 inputArea.style.left = '0';
            }
        }
    }

    
    // --- 2. Dark Theme Toggle Logic ---
    if (themeToggle) {
        // Apply saved theme on page load 
        if (localStorage.getItem(THEME_KEY) === 'light') {
            // If the user prefers light mode, we can add a class
            // (You'd need to add '.light-theme' CSS rules to your stylesheet)
            body.classList.add('light-theme');
        }

        themeToggle.addEventListener('click', function(e) {
            e.preventDefault(); 
            
            // Toggle the theme class (using light-theme for visual change)
            body.classList.toggle('light-theme');
            
            // Save the new preference
            if (body.classList.contains('light-theme')) {
                localStorage.setItem(THEME_KEY, 'light');
            } else {
                localStorage.setItem(THEME_KEY, 'dark');
            }
            
        });
    }


    // --- 3. Chat Submission Logic ---
    if (chatForm && messageInput && chatBox && chatIDElement) {
        chatForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const message = messageInput.value.trim();
            const chat_id = chatIDElement.value;

            if (message === "") return;

            // Display user message immediately
            appendMessage('user', message);
            messageInput.value = ''; // Clear input field
            messageInput.style.height = '20px'; // Reset input height

            // Show a temporary loading indicator
            const loadingIndicator = appendMessage('model', '...', true);

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ message: message, chat_id: chat_id })
                });

                const data = await response.json();

                // Remove loading indicator
                chatBox.removeChild(loadingIndicator);

                if (data.error) {
                    appendMessage('model', 'Error: ' + data.error);
                } else {
                    appendMessage('model', data.response);
                }

            } catch (error) {
                // Ensure the loading indicator is removed on failure too
                if (chatBox.contains(loadingIndicator)) {
                     chatBox.removeChild(loadingIndicator);
                }
                console.error('Error sending message:', error);
                appendMessage('model', 'An error occurred while connecting to the AI. Check server logs.');
            }
        });
    }


    function appendMessage(role, text, isLoading = false) {
        const messageContainer = document.createElement('div');
        messageContainer.className = 'message-container ' + role;

        const messageBubble = document.createElement('div');
        messageBubble.className = 'message-bubble';
        
        if (isLoading) {
            messageBubble.classList.add('loading');
        }
        
        // Safely insert text content, then replace newlines with <br>
        // This is safe from XSS because we use textContent before using innerHTML
        messageBubble.textContent = text; 
        messageBubble.innerHTML = messageBubble.textContent.replace(/\n/g, '<br>');

        messageContainer.appendChild(messageBubble);
        chatBox.appendChild(messageContainer);
        chatBox.scrollTop = chatBox.scrollHeight; // Auto-scroll to bottom

        return messageContainer;
    }
});