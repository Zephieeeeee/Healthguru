import os
import uuid
import json
from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from datetime import datetime
from google import genai
from google.genai.errors import APIError

# --- Configuration & Initialization ---

# Use environment variable for API Key
# Note: For Canvas deployment, the API key is handled automatically if left blank.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
client = genai.Client(api_key=GEMINI_API_KEY)

# Flask App setup
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a_very_secret_key_for_session")

# --- Helper Functions for Session Management ---

def get_chat_model():
    """Returns the Gemini chat model instance."""
    # Use gemini-2.5-flash for speed and general Q&A
    return client.chats.create(model="gemini-2.5-flash")

def get_or_create_chat(chat_id=None):
    """
    Retrieves a chat session from Flask session or creates a new one.
    If chat_id is None, it creates a new one.
    """
    if 'history' not in session:
        session['history'] = {}

    if chat_id and chat_id in session['history']:
        # Load existing chat
        current_chat = session['history'][chat_id]
        return chat_id, current_chat
        
    # Create new chat
    new_chat_id = str(uuid.uuid4())
    new_chat_session = {
        'id': new_chat_id,
        'messages': [],
        'created_at': datetime.now().isoformat(),
        'title': 'New Chat'
    }
    session['history'][new_chat_id] = new_chat_session
    session.modified = True
    return new_chat_id, new_chat_session

def get_all_chats_for_sidebar():
    """Returns all chats, sorted reverse chronologically."""
    history = session.get('history', {})
    
    # Sort history by creation time (the 'created_at' field)
    sorted_chats = sorted(
        history.values(), 
        key=lambda x: datetime.fromisoformat(x.get('created_at', datetime.min.isoformat())),
        reverse=True
    )
    return sorted_chats

# --- Routes and Logic ---

@app.route('/', defaults={'chat_id': None})
@app.route('/chat/<chat_id>')
def Index(chat_id):
    """Renders the main chat interface and loads or starts a chat session."""
    
    # 1. Get the list of all chats for the sidebar
    all_history = get_all_chats_for_sidebar()
    
    # 2. FIX: Prevent new chat creation on '/' refresh if history exists
    if chat_id is None:
        if all_history:
            # If we land on '/' and history exists, redirect to the latest chat
            latest_chat_id = all_history[0]['id']
            return redirect(url_for('Index', chat_id=latest_chat_id))
            
    # 3. Get or create the current chat
    current_chat_id, current_chat = get_or_create_chat(chat_id)
    messages = current_chat['messages']
    
    return render_template('index.html',
        messages=messages,
        current_chat_id=current_chat_id,
        recent_chats=all_history
    )

@app.route('/new_chat')
def new_chat():
    """Starts a brand new, empty chat session."""
    # Explicitly create a new chat and redirect to its ID
    new_id, _ = get_or_create_chat(None)
    return redirect(url_for('Index', chat_id=new_id))


@app.route('/chat', methods=['POST'])
def chat():
    """Handles the chat message, sends to Gemini, and returns response."""
    try:
        data = request.get_json()
        user_message = data.get("message")
        chat_id = data.get("chat_id")

        current_chat_id, current_chat = get_or_create_chat(chat_id)
        
        # Add user message to history
        current_chat['messages'].append({
            'role': 'user', 
            'parts': [{'text': user_message}]
        })
        
        # Construct chat history for the API call
        history_parts = []
        for msg in current_chat['messages']:
             history_parts.append({"role": msg['role'], "parts": msg['parts']})
             
        # Call Gemini API using generateContent with history
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=history_parts,
            config={"system_instruction": "You are Healthguru, an AI trained to offer general, non-diagnostic health and wellness information. Always preface your responses with a strong disclaimer that you are not a medical professional."}
        )
        
        # Add model response to history
        model_response = response.text
        current_chat['messages'].append({
            'role': 'model', 
            'parts': [{'text': model_response}]
        })
        
        # Initial title generation (only for new chats)
        if current_chat.get('title') == 'New Chat' and len(current_chat['messages']) == 2:
            # Try to generate a concise title based on the first user message
            title_response = client.models.generate_content(
                model='gemini-2.5-flash', 
                contents=[
                    {"role": "user", "parts": [{"text": f"Create a short, three-word maximum, title for this chat topic: '{user_message}'"}]}
                ]
            )
            current_chat['title'] = title_response.text.strip().replace('"', '')

        session.modified = True
        return jsonify(response=model_response, chat_id=current_chat_id)

    except APIError as e:
        print(f"Gemini API Error: {e}")
        return jsonify(error="A problem occurred with the AI service. Please try again."), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify(error="An unexpected error occurred."), 500

# --- NEW ROUTE: DELETE CHAT ---
@app.route('/delete_chat/<chat_id>', methods=['POST'])
def delete_chat(chat_id):
    """Deletes a chat session from the history."""
    if 'history' in session and chat_id in session['history']:
        del session['history'][chat_id]
        session.modified = True
        
        # After deletion, find the next chat to load or redirect to new chat
        all_history = get_all_chats_for_sidebar()
        
        if all_history:
            # Redirect to the next most recent chat
            redirect_id = all_history[0]['id']
            return jsonify(success=True, redirect_url=url_for('Index', chat_id=redirect_id))
        else:
            # Redirect to create a brand new chat
            return jsonify(success=True, redirect_url=url_for('Index'))
            
    return jsonify(success=False, error="Chat not found"), 404