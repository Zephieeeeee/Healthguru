import os
import uuid
import json
from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from datetime import datetime, MINYEAR
from google import genai
from google.genai.errors import APIError
from dotenv import load_dotenv # <-- IMPORT IS NOW AT THE TOP

# --- Configuration & Initialization ---

load_dotenv() # <-- FUNCTION IS NOW CALLED *AFTER* IMPORT

# Use environment variable for API Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
client = genai.Client(api_key=GEMINI_API_KEY)

# Flask App setup
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a_very_secret_key_for_session")

# --- Helper Functions for Session Management ---

def get_chat_model():
    """Returns the Gemini chat model instance."""
    return client.chats.create(model="gemini-2.5-flash")

def get_or_create_chat(chat_id=None):
    """
    Retrieves a chat session from Flask session or creates a new one.
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
    """
    Returns all chats, sorted reverse chronologically, 
    ensuring all chat objects are valid and have a title.
    """
    history = session.get('history', {})
    clean_chats = []
    
    # Use a default minimum datetime for sorting entries that might be malformed
    min_datetime = datetime(MINYEAR, 1, 1).isoformat()
    
    for chat_id, chat_data in history.items():
        if not isinstance(chat_data, dict):
            continue # Skip malformed, old session data
        
        # Ensure essential keys exist on all chat objects
        chat_data['id'] = chat_data.get('id', chat_id)
        chat_data['created_at'] = chat_data.get('created_at', min_datetime)
        
        # If 'title' is missing or blank, provide a default
        if not chat_data.get('title'):
            chat_data['title'] = 'Untitled Chat'
        # Fix for chats that were new but never got a message
        elif chat_data['title'] == 'New Chat' and not chat_data.get('messages'):
             chat_data['title'] = 'Untitled Chat'
        
        clean_chats.append(chat_data)

    # Sort the clean list by creation time
    sorted_chats = sorted(
        clean_chats, 
        key=lambda x: datetime.fromisoformat(x['created_at']),
        reverse=True
    )
    return sorted_chats

# --- Routes and Logic ---

@app.route('/', defaults={'chat_id': None})
@app.route('/chat/<chat_id>')
def Index(chat_id):
    """Renders the main chat interface and loads or starts a chat session."""
    
    all_history = get_all_chats_for_sidebar()
    
    # FIX: "New Chat on Refresh"
    if chat_id is None:
        if all_history:
            # If user visits "/" and has history, redirect to the most recent chat
            latest_chat_id = all_history[0]['id']
            return redirect(url_for('Index', chat_id=latest_chat_id))
            
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
        
        current_chat['messages'].append({
            'role': 'user', 
            'parts': [{'text': user_message}]
        })
        
        history_parts = []
        for msg in current_chat['messages']:
             history_parts.append({"role": msg['role'], "parts": msg['parts']})
             
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=history_parts,
            config={"system_instruction": "You are Healthguru, an AI trained to offer general, non-diagnostic health and wellness information. Always preface your responses with a strong disclaimer that you are not a medical professional."}
        )
        
        model_response = response.text
        current_chat['messages'].append({
            'role': 'model', 
            'parts': [{'text': model_response}]
        })
        
        if current_chat.get('title') == 'New Chat' and len(current_chat['messages']) == 2:
            title_response = client.models.generate_content(
                model='gemini-2.5-flash', 
                contents=[
                    {"role": "user", "parts": [{"text": f"Create a short, three-word maximum, title for this chat topic: '{user_message}'"}]}
                ]
            )
            new_title = title_response.text.strip().replace('"', '')
            current_chat['title'] = new_title if new_title else 'Chat'

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
        
        all_history = get_all_chats_for_sidebar()
        
        if all_history:
            # Redirect to the next most recent chat
            redirect_id = all_history[0]['id']
            return jsonify(success=True, redirect_url=url_for('Index', chat_id=redirect_id))
        else:
            # No chats left, redirect to root (which will create a new one)
            return jsonify(success=True, redirect_url=url_for('Index'))
            
    return jsonify(success=False, error="Chat not found"), 404