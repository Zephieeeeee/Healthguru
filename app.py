import os
import uuid
from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from dotenv import load_dotenv

# --- Load Environment Variables ---
# This ensures FLASK_SECRET_KEY and GEMINI_API_KEY are loaded from .env
load_dotenv()

# --- CORRECTED GEMINI SDK IMPORTS ---
# We import the client directly, which is the most stable method
from google.genai.client import Client as GeminiClient
from google.genai.errors import APIError

# --- Instantiate the Client Globally ---
# The client automatically picks up the GEMINI_API_KEY from the environment
try:
    gemini_client = GeminiClient()
except Exception as e:
    # Log an error if the API key setup fails before the app starts
    print(f"Error initializing Gemini client: {e}")
    print("Please ensure GEMINI_API_KEY is set correctly in your .env file or Render environment variables.")

# --- Flask App Initialization ---
app = Flask(__name__)
# The secret key is essential for Flask sessions (chat history)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default-fallback-secret-key')


# --- Helper Function for Chat Initialization ---
def get_or_create_chat(chat_id):
    """
    Initializes a new chat session using the GeminiClient or retrieves an existing one.
    The session is stored in the Flask user session.
    """
    if 'history' not in session:
        session['history'] = {}

    if chat_id is None or chat_id not in session['history']:
        try:
            # Create a new chat session with the correct model
            # gemini-2.5-flash is fast and cost-effective for chat
            chat_session = gemini_client.chats.create(model="gemini-2.5-flash")

            # Generate a new ID and initial state
            new_id = str(uuid.uuid4())
            new_title = "New Chat"

            session['history'][new_id] = {
                'chat_session': chat_session,
                'title': new_title,
                'messages': [
                    {
                        "role": "model",
                        "parts": [{"text": "Hello! I'm Healthguru, an AI trained to offer general health and wellness information. How can I assist you today?"}]
                    }
                ]
            }
            session.modified = True
            return new_id, session['history'][new_id]
        except Exception as e:
            print(f"Error creating new chat session: {e}")
            # Fallback for errors (e.g., if API key is invalid)
            return "error", {'chat_session': None, 'title': 'Error', 'messages': [{'role': 'model', 'parts': [{'text': f'AI Initialization Error: {e}'}]}]}


    return chat_id, session['history'][chat_id]


# --- Routes and Logic ---

@app.route('/', defaults={'chat_id': None})
@app.route('/chat/<chat_id>')
def index(chat_id):
    """Renders the main chat interface and loads or starts a chat session."""
    current_chat_id, current_chat = get_or_create_chat(chat_id)
    
    # Handle the error case
    if current_chat_id == "error":
        messages = current_chat['messages']
    else:
        messages = current_chat['messages']

    # Send all history items for the sidebar, sorted by last message time (or title if no messages)
    # Note: Using a simple title sort since message timestamps are complex to manage in Flask session
    all_history = sorted(
        session.get('history', {}).items(),
        key=lambda item: item[1]['title'],
        reverse=False
    )
    
    return render_template(
        'index.html',
        messages=messages,
        current_chat_id=current_chat_id,
        all_history=all_history
    )

@app.route('/new_chat')
def new_chat():
    """Starts a brand new, empty chat session."""
    # Simply redirecting to the index route with no chat_id will create a new one
    return redirect(url_for('index'))

@app.route('/chat', methods=["POST"])
def chat():
    """Handles the chat message, sends to Gemini, and returns response."""
    try:
        data = request.json
        user_message = data["message"]
        chat_id = data["chat_id"]
        
        current_chat_id, current_chat = get_or_create_chat(chat_id)

        # Check if chat session initialization failed
        if current_chat['chat_session'] is None:
            return jsonify({'error': 'AI client not ready. Check API key.'}), 500

        # Append user message to history
        current_chat['messages'].append({"role": "user", "parts": [{"text": user_message}]})

        # --- FIX 2: Correct call to send_message ---
        # The send_message function in the new SDK accepts only the content (user_message)
        response = current_chat['chat_session'].send_message(user_message)
        
        # Check if this is the first message (title creation logic)
        if len(current_chat['messages']) == 2: # 1st message is the welcome, 2nd is user's first query
            # Prompt the model to generate a title asynchronously (optional, but good practice)
            # For simplicity, we'll just set it to the first few words of the message for now
            current_chat['title'] = user_message[:30] + '...' if len(user_message) > 30 else user_message
        
        # Append model response to history
        # We use .to_dict() to save the response object in a JSON-serializable format in the session
        current_chat['messages'].append(response.to_dict())
        session.modified = True

        return jsonify({'response': response.text, 'chat_id': current_chat_id})

    except APIError as e:
        # Handle specific API errors (e.g., quota exceeded)
        print(f"AI Error: {e}")
        return jsonify({'error': f'AI Service Error: {e.message}'}), 500
    except Exception as e:
        # Handle all other exceptions (e.g., JSON parse error, network issue)
        print(f"Chat function error: {e}")
        return jsonify({'error': 'An unexpected error occurred.'}), 500

if __name__ == '__main__':
    # Flask runs in debug mode locally
    app.run(debug=True)
