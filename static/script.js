
document.addEventListener('DOMContentLoaded', function() {
    
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


    if (openSidebarBtn && closeSidebarBtn && sidebar) {
        openSidebarBtn.addEventListener('click', () => {
            sidebar.classList.add('open');
            body.style.overflow = 'hidden'; 
            updateInputAreaWidth();
        });

        closeSidebarBtn.addEventListener('click', () => {
            sidebar.classList.remove('open');
            body.style.overflow = '';
            updateInputAreaWidth();
        });
        
        window.addEventListener('resize', () => {
            if (window.innerWidth > 768) {
                sidebar.classList.remove('open');
                body.style.overflow = '';
            }
            updateInputAreaWidth();
        });
    }

    function updateInputAreaWidth() {
        const inputArea = document.getElementById('input-area');
        if (sidebar && inputArea) {
             const sidebarIsVisible = window.innerWidth > 768 || sidebar.classList.contains('open');
            
            if (sidebarIsVisible) {
                inputArea.style.width = `calc(100% - ${sidebar.offsetWidth}px)`;
                inputArea.style.left = `${sidebar.offsetWidth}px`;
            } else {
                 inputArea.style.width = '100%';
                 inputArea.style.left = '0';
            }
        }
    }

    
    if (themeToggle) {
        if (localStorage.getItem(THEME_KEY) === 'light') {
            body.classList.add('light-theme');
        }

        themeToggle.addEventListener('click', function(e) {
            e.preventDefault(); 
            
            body.classList.toggle('light-theme');
            
            if (body.classList.contains('light-theme')) {
                localStorage.setItem(THEME_KEY, 'light');
            } else {
                localStorage.setItem(THEME_KEY, 'dark');
            }
            
        });
    }


    if (chatForm && messageInput && chatBox && chatIDElement) {
        chatForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const message = messageInput.value.trim();
            const chat_id = chatIDElement.value;

            if (message === "") return;

            appendMessage('user', message);
            messageInput.value = ''; 
            messageInput.style.height = '20px'; 

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

                chatBox.removeChild(loadingIndicator);

                if (data.error) {
                    appendMessage('model', 'Error: ' + data.error);
                } else {
                    appendMessage('model', data.response);
                }

            } catch (error) {
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
        
        
        messageBubble.textContent = text; 
        messageBubble.innerHTML = messageBubble.textContent.replace(/\n/g, '<br>');

        messageContainer.appendChild(messageBubble);
        chatBox.appendChild(messageContainer);
        chatBox.scrollTop = chatBox.scrollHeight; 

        return messageContainer;
    }
});
