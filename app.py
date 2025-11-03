import os
import uuid
from dotenv import load_dotenv
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

# --- Configuration Section ---

load_dotenv() 

app = Flask(__name__)

# IMPORTANT: Set a secret key for Flask Sessions. 
# Ensure FLASK_SECRET_KEY is set in your .env file!
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a_very_secret_key_that_should_be_changed")

# Configure the Gemini API key
try:
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise AttributeError("GEMINI_API_KEY not found. Please set it in your .env file.")
        
    genai.configure(api_key=gemini_key)

except AttributeError as e:
    print(f"Error: {e}")
    exit()

# Set up the generative model
MODEL_NAME = 'gemini-2.5-flash'

# Define the system instruction once
SYSTEM_INSTRUCTION = """
IMPORTANT: YOU ARE A HELPFUL AI WELLNESS ASSISTANT, NOT A DOCTOR.
- DO NOT provide a diagnosis.
- DO NOT provide medical advice.
- ALWAYS start your response with the following disclaimer:
  "I am an AI assistant and not a medical professional. This information is not a diagnosis. Please consult a doctor for medical advice."
"""


# --- Session Management Functions ---

def get_or_create_chat(chat_id=None):
    """Initializes a new chat or retrieves an existing one from session."""
    
    # 1. Base model configuration (includes the system instruction)
    model = genai.GenerativeModel(
        model_name=MODEL_NAME, 
        system_instruction=SYSTEM_INSTRUCTION # System instruction applied here
    )
    
    # Check if a chat ID was provided (for loading history)
    if chat_id and chat_id in session.get('history', {}):
        chat_data = session['history'][chat_id]
        # Create a new ChatSession with the existing history
        chat = model.start_chat(history=chat_data['messages'])
        return chat_id, chat
        
    # Start a NEW chat session
    new_chat_id = str(uuid.uuid4())
    
    # Initialize the Gemini Chat object
    new_chat = model.start_chat()
    
    # Store initial data for the new chat
    if 'history' not in session:
        session['history'] = {}

    session['history'][new_chat_id] = {
        'id': new_chat_id,
        'title': 'New Chat',
        'messages': []
    }
    
    return new_chat_id, new_chat

def update_chat_history(chat_id, user_message, bot_response_text):
    """Updates Flask session history with new messages."""
    
    if chat_id not in session['history']:
        return
        
    chat_entry = session['history'][chat_id]
    
    # Store messages
    chat_entry['messages'].append({"role": "user", "parts": [{"text": user_message}]})
    chat_entry['messages'].append({"role": "model", "parts": [{"text": bot_response_text}]})

    # Set the chat title using the first message if it's still 'New Chat'
    title_updated = False
    if chat_entry['title'] == 'New Chat' and user_message:
        chat_entry['title'] = user_message[:30] + ('...' if len(user_message) > 30 else '')
        title_updated = True

    session.modified = True
    
    return title_updated, chat_entry


# --- Routes and Logic ---

@app.route('/', defaults={'chat_id': None})
@app.route('/chat/<chat_id>')
def index(chat_id):
    """Renders the main chat interface and loads or starts a chat session."""
    
    current_chat_id, current_chat = get_or_create_chat(chat_id)
    messages = session['history'][current_chat_id]['messages']
    
    # Send all history items for the sidebar
    all_history = sorted(
        session.get('history', {}).values(), 
        key=lambda x: x['messages'][-1]['parts'][0]['text'] if x['messages'] else '',
        reverse=False
    )
    
    return render_template('index.html', 
                           messages=messages, 
                           current_chat_id=current_chat_id, 
                           history=all_history)

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

        # 1. Send the message to Gemini (NO 'config' ARGUMENT USED HERE)
        response = current_chat.send_message(user_message)

        bot_response_text = response.text

        # 2. Update session history and check if the title was set
        title_updated, chat_entry = update_chat_history(current_chat_id, user_message, bot_response_text)
        
        # 3. Render the new history item HTML if the title was updated
        history_item_html = ""
        if title_updated:
            history_item_html = render_template('_history_item.html', chat=chat_entry, current_chat_id=current_chat_id)
        
        # 4. Return the response data
        return jsonify({
            "response": bot_response_text,
            "chat_id": current_chat_id,
            "title_updated": title_updated,
            "new_history_html": history_item_html,
            "new_title": chat_entry['title'] if title_updated else None
        })
    
    except Exception as e:
        # This will catch and print any errors *during* the chat message processing
        print(f"Error in chat function: {e}") 
        return jsonify({"response": "Sorry, I encountered an error and cannot reply. Check the terminal for details."}), 500

# --- Server Execution ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)