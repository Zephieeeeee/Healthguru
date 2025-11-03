import os
import uuid
from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from dotenv import load_dotenv

# Import the correct client library
from google import genai
from google.genai.errors import APIError

# --- Initialization and Configuration ---

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
# The secret key is essential for Flask session management
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a_super_secret_fallback_key_dont_use_in_prod")

# Initialize the Gemini Client
# The client will automatically pick up the GEMINI_API_KEY from the environment
try:
    client = genai.Client()
except Exception as e:
    # Handle case where API Key is missing or invalid
    print(f"Error initializing Gemini Client: {e}")
    client = None

# Model Configuration
MODEL_NAME = 'gemini-2.5-flash'
SYSTEM_INSTRUCTION = (
    "You are HealthGuru, an AI Wellness Companion. Your primary goal is to provide "
    "general, educational, and helpful information about health, fitness, nutrition, and well-being. "
    "Always include a strong disclaimer: 'I am an AI, not a medical professional. "
    "Consult a qualified healthcare provider for any medical advice or diagnosis.' "
    "Keep responses encouraging and easy to understand. Only use Google Search grounding if absolutely necessary."
)

# --- Chat Session Management ---

def get_or_create_chat(chat_id=None):
    """
    Retrieves an existing chat session from Flask session or creates a new one.
    This also handles the re-initialization of the Gemini model.
    """
    if chat_id is None:
        # Create a new unique ID for the chat
        chat_id = str(uuid.uuid4())
        session['history'] = session.get('history', {})
        session['history'][chat_id] = {
            'messages': [],
            'title': 'New Chat',
            'model': None
        }

    chat_data = session['history'].get(chat_id)

    if not chat_data:
        # If ID was provided but data is missing (e.g., session cleared), create a new one
        return get_or_create_chat(None)

    # 1. Initialize/Re-initialize the Model and ChatSession
    # We do this here to ensure the session object is always valid
    if client and (chat_data.get('model') is None or chat_data.get('model').model_name != MODEL_NAME):
        # Create a new model instance
        model = client.models.generate_content(
            model=MODEL_NAME,
            system_instruction=SYSTEM_INSTRUCTION,
            # Tools (like google_search) are now passed during the chat session creation
            # to avoid the startup error.
        )
        
        # Start a new chat session, loading the past history
        chat_session = client.chats.create(
            model=MODEL_NAME,
            history=chat_data['messages'],
            config={"system_instruction": SYSTEM_INSTRUCTION, "tools": [{"google_search": {}}]}
        )
        
        # Store the live chat session object in the chat data dictionary
        # NOTE: We are storing the entire chat session object here for simplicity. 
        # In a production app, you might serialize the history separately.
        chat_data['model'] = chat_session 
    
    return chat_id, chat_data

# --- Routes and Logic ---

@app.route('/', defaults={'chat_id': None})
@app.route('/chat/<chat_id>')
def index(chat_id):
    """Renders the main chat interface and loads or starts a chat session."""
    
    current_chat_id, current_chat = get_or_create_chat(chat_id)
    
    # Extract messages to pass to the template
    messages = current_chat['messages']
    
    # Send all history items for the sidebar
    # Sort history by last message timestamp (or just keep creation order)
    all_history = sorted(
        session.get('history', {}).items(),
        key=lambda item: item[1]['messages'][-1]['timestamp'] if item[1]['messages'] else 0, # Placeholder key
        reverse=True
    )
    
    # Add a welcome message if the chat is brand new
    if not messages:
        welcome_message = {
            'role': 'model',
            'parts': [{'text': "Hello! I'm HealthGuru, an AI trained to offer general health and wellness information. How can I assist you today?"}],
            'timestamp': os.times().user
        }
        messages.append(welcome_message)
        # Update the session with the initial message
        current_chat['messages'] = messages
        session.modified = True

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
    
    if not client:
        return jsonify({"error": "Gemini client not initialized. Check API Key."}), 500

    try:
        # 1. Get user message and chat ID
        data = request.json
        user_message = data['message']
        chat_id = data['chat_id']
        
        # 2. Get the current chat session
        current_chat_id, current_chat = get_or_create_chat(chat_id)
        chat_session = current_chat['model']
        
        # 3. Add user message to history (optional, as send_message adds it)
        # It's cleaner to let the send_message call handle history update, 
        # but we add it here manually to ensure it's in the session immediately.
        user_message_part = {
            'role': 'user', 
            'parts': [{'text': user_message}],
            'timestamp': os.times().user # Using os.times() as a simple timestamp placeholder
        }
        current_chat['messages'].append(user_message_part)
        
        # 4. Send message to the Gemini API
        # FIX: The 'config' argument has been removed to fix the 500 error.
        response = chat_session.send_message(user_message)

        # 5. Add model response to history
        model_response_part = {
            'role': 'model', 
            'parts': [{'text': response.text}],
            'timestamp': os.times().user
        }
        current_chat['messages'].append(model_response_part)
        
        # 6. Update chat title if it's still 'New Chat'
        if current_chat.get('title') == 'New Chat':
            # Use the model to summarize the chat title based on the first turn
            # This is a good place to use a separate, very fast model (like gemini-2.5-flash)
            # You might want to skip this step initially for speed.
            pass # Skipping auto-title for now to keep it simple.

        # 7. Mark session as modified to save changes
        session.modified = True
        
        # 8. Return the model response text
        return jsonify({"response": response.text})

    except APIError as e:
        print(f"Gemini API Error: {e}")
        return jsonify({"error": f"An API error occurred: {e}"}), 500
    except Exception as e:
        print(f"Error in chat function: {e}")
        # This will now print the error to your server console instead of returning a 500, 
        # allowing for better debugging.
        return jsonify({"error": f"An internal error occurred: {e}"}), 500


if __name__ == '__main__':
    # Flask runs the app from this file
    app.run(debug=True)