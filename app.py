import os
import uuid
import json 
from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from dotenv import load_dotenv

# Ensure the correct client library import path
from google.genai.client import Client as GeminiClient
from google.genai.errors import APIError

# --- Initial Setup ---
load_dotenv()

app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", 'super_secret_fallback_key') # Use fallback if not set

# Initialize the Gemini Client globally
try:
    # Client initialized here handles the API Key from environment variables
    gemini_client = GeminiClient()
    print("Gemini Client Initialized Successfully.")
except Exception as e:
    print(f"Error initializing Gemini Client: {e}")
    gemini_client = None


def get_or_create_chat_id(chat_id=None):
    """
    Retrieves a chat session from the session or creates a new one.
    The session stores a simple dictionary containing 'messages'.
    """
    if 'history' not in session:
        session['history'] = {}

    if chat_id in session['history']:
        # Return existing chat data (simple dictionary)
        return chat_id, session['history'][chat_id]
    
    # Create new chat
    new_chat_id = str(uuid.uuid4())
    session['history'][new_chat_id] = {
        'messages': [],
        'model_name': 'gemini-2.5-flash' # Default model
    }
    session.modified = True
    # Return the new chat data (simple dictionary)
    return new_chat_id, session['history'][new_chat_id]


# --- Routes and Logic ---

@app.route('/', defaults={'chat_id': None})
@app.route('/chat/<chat_id>')
def index(chat_id):
    """
    Renders the main chat interface and loads or starts a chat session.
    """
    # This function is fine now, as it returns a serializable dictionary
    current_chat_id, current_chat = get_or_create_chat_id(chat_id)
    messages = current_chat['messages']

    # Simple list of recent titles for sidebar.
    recent_chats = []
    # **BUG FIX**: We must only iterate over the keys and then look up the data.
    # We must ensure all history items are simple dictionaries, not complex objects.
    
    # Get all history items from the session
    all_history_items = session.get('history', {})
    
    for cid, chat_data in all_history_items.items():
        if chat_data['messages']:
            # Use the first user message text as the title
            try:
                # Find the first user message for a clean title
                first_message = next(
                    (msg['parts'][0]['text'] for msg in chat_data['messages'] if msg['role'] == 'user'),
                    "New Chat"
                )
            except:
                first_message = "New Chat (Error reading content)"
                
            title = first_message
            # Limit title length for sidebar
            recent_chats.append({'id': cid, 'title': title[:30] + '...' if len(title) > 30 else title})
        else:
            # Handle empty chat history
            recent_chats.append({'id': cid, 'title': "New Chat"})

    # Sort the recent chats by creation/last access time if possible, or just alphabetically for now
    recent_chats.sort(key=lambda x: x['title'])


    return render_template(
        'index.html',
        messages=messages,
        current_chat_id=current_chat_id,
        recent_chats=recent_chats 
    )

@app.route('/new_chat')
def new_chat():
    """
    Starts a brand new, empty chat session.
    """
    return redirect(url_for('index'))

@app.route('/chat', methods=['POST'])
def chat():
    """
    Handles the chat message, sends to Gemini, and returns response.
    """
    if gemini_client is None:
        return jsonify({"error": "Gemini Client failed to initialize. Check API Key/Dependencies."}), 500

    try:
        data = request.json
        user_message = data['message']
        chat_id = data['chat_id']

        current_chat_id, current_chat = get_or_create_chat_id(chat_id)
        
        # 1. Add user message to history
        current_chat['messages'].append({
            "role": "user",
            "parts": [{"text": user_message}]
        })
        
        # 2. Call Gemini
        # We pass the full message history (a list of dictionaries) to maintain context
        response = gemini_client.models.generate_content(
            model=current_chat['model_name'],
            contents=current_chat['messages']
        )
        
        ai_response_text = response.text
        
        # 3. Add AI message to history
        current_chat['messages'].append({
            "role": "model",
            "parts": [{"text": ai_response_text}]
        })
        
        # 4. Save the modified session (which only contains serializable dictionaries)
        session.modified = True
        
        # 5. Return the new AI response
        return jsonify({"response": ai_response_text, "chat_id": current_chat_id})

    except APIError as e:
        print(f"Gemini API Error: {e}")
        return jsonify({"error": f"An API error occurred: {e}"}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500


if __name__ == '__main__':
    app.run(debug=True)