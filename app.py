import os
import json
import time
import random
import string
from flask import Flask, request, jsonify, render_template, redirect, url_for
from google import genai
from google.genai import types

# --- Configuration and Initialization ---

app = Flask(__name__)
# The API key is set via environment variable GEMINI_API_KEY in the deployment environment.
# If running locally, you must set it in your environment.
# The client automatically picks up the key.
try:
    client = genai.Client()
    print("Gemini Client initialized successfully.")
except Exception as e:
    print(f"Error initializing Gemini Client: {e}")
    client = None

# In-memory storage for chat sessions. 
# Key: chat_id (string), Value: list of message parts (Gemini format)
chat_sessions = {}
# Key: chat_id (string), Value: chat title (string)
chat_titles = {}
# Key: chat_id (string), Value: timestamp (float)
chat_timestamps = {}

# System instruction for the Healthguru model
HEALTHGURU_SYSTEM_INSTRUCTION = (
    "You are 'Healthguru', an AI-powered wellness and general health information assistant. "
    "Your primary role is to provide well-researched, general, and easy-to-understand information based on the user's queries. "
    "Crucial Mandate: You are NOT a medical professional. ALWAYS include a prominent disclaimer in your response that the user must consult a qualified doctor or healthcare provider for personalized medical advice, diagnosis, or treatment. "
    "Your tone should be empathetic, supportive, and informative, focusing on widely accepted non-critical wellness practices, first aid basics, and common ailment management (e.g., home remedies, rest recommendations). "
    "Format your responses clearly using Markdown (bold, lists, etc.) to enhance readability."
)

# --- Utility Functions ---

def generate_chat_id():
    """Generates a unique, short ID for a new chat session."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))

def get_recent_chats():
    """Returns a list of recent chats with titles and IDs, sorted by timestamp."""
    recent = []
    for chat_id, title in chat_titles.items():
        recent.append({
            'id': chat_id,
            'title': title,
            'timestamp': chat_timestamps.get(chat_id, 0)
        })
    # Sort by timestamp, newest first
    recent.sort(key=lambda x: x['timestamp'], reverse=True)
    return recent[:10] # Limit to 10 recent chats

def generate_title_from_message(user_message):
    """
    Uses the Gemini API to generate a concise, descriptive title 
    for the chat based on the user's first message.
    """
    if not client:
        return "Untitled Chat"

    # Limit the prompt length to ensure it's fast and focused
    prompt = f"Condense the following user message into a very concise, three-word maximum title for a chat history list. The message is: \"{user_message[:100]}...\""
    
    try:
        # Use a very fast model for a quick, simple title
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="You are a title generator. Output only the short title text, with no quotes or extraneous punctuation."
            )
        )
        # Clean up the response to ensure it's a clean string
        title = response.text.strip().replace('"', '')
        return title if len(title) > 0 else "New Health Query"
    except Exception as e:
        print(f"Error generating chat title: {e}")
        return "New Health Query" # Fallback title


def save_chat_history(chat_id, history, title):
    """
    Stores the chat history, updates the title, and sets the timestamp.
    If the chat is brand new (title is 'New Health Query'), it generates a proper title.
    """
    chat_sessions[chat_id] = history
    
    # 1. Update timestamp for sorting
    chat_timestamps[chat_id] = time.time()
    
    # 2. Update title if needed
    # We only generate a title if the current title is the default one and the history has content.
    if title == "New Health Query" and len(history) > 1 and history[-1].role == 'model':
        # The first message from the user is at index 0
        first_user_message = history[0].parts[0].text
        new_title = generate_title_from_message(first_user_message)
        chat_titles[chat_id] = new_title
    else:
        chat_titles[chat_id] = title

# --- Flask Routes ---

@app.route('/')
def index():
    """Redirects to a new chat session."""
    return redirect(url_for('new_chat'))

@app.route('/new_chat')
def new_chat():
    """Initializes and displays a new, empty chat session."""
    new_id = generate_chat_id()
    # Initialize chat session with a placeholder for the title
    chat_sessions[new_id] = []
    # Set the initial title to a temporary, easy-to-identify value
    chat_titles[new_id] = "New Health Query"
    chat_timestamps[new_id] = time.time()
    return redirect(url_for('chat_view', chat_id=new_id))

@app.route('/chat/<chat_id>')
def chat_view(chat_id):
    """Displays an existing chat session."""
    if chat_id not in chat_sessions:
        return redirect(url_for('new_chat'))

    # Convert the internal chat history to a format for the template
    messages = [
        {'role': msg.role, 'parts': [{'text': part.text}]}
        for msg in chat_sessions[chat_id]
        for part in msg.parts if hasattr(part, 'text')
    ]

    return render_template(
        'index.html',
        messages=messages,
        current_chat_id=chat_id,
        recent_chats=get_recent_chats()
    )

@app.route('/chat', methods=['POST'])
def chat_api():
    """Handles the API call to the Gemini model."""
    data = request.json
    user_message = data.get('message', '').strip()
    chat_id = data.get('chat_id')

    if not user_message:
        return jsonify({'error': 'Message cannot be empty'}), 400
    
    # If the chat ID is new or invalid, initialize a new session
    if chat_id not in chat_sessions:
        chat_id = generate_chat_id()
        chat_sessions[chat_id] = []
        chat_titles[chat_id] = "New Health Query"
        chat_timestamps[chat_id] = time.time()

    # Get the current history for this session
    history = chat_sessions[chat_id]

    # Add the user's message to the history (Gemini format)
    history.append(types.Content(role="user", parts=[types.Part.from_text(user_message)]))

    # --- Call Gemini API ---
    if not client:
        return jsonify({'error': 'AI service not initialized.'}), 500

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash', # Use flash for fast, conversational responses
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=HEALTHGURU_SYSTEM_INSTRUCTION
            )
        )

        # Add the model's response to the history
        history.append(response.candidates[0].content)
        
        # Save the updated history and potentially generate a title
        save_chat_history(chat_id, history, chat_titles.get(chat_id, "New Health Query"))

        # Extract the text from the model's response
        model_text = response.text

        # Return the AI response and the chat_id (which might be new)
        return jsonify({
            'response': model_text,
            'chat_id': chat_id
        })

    except Exception as e:
        print(f"Gemini API Error: {e}")
        # Remove the last user message from history if the API call failed
        history.pop()
        return jsonify({'error': 'Failed to communicate with the AI model. Please try again.'}), 500

@app.route('/delete_chat/<chat_id>', methods=['POST'])
def delete_chat(chat_id):
    """Deletes a chat session and redirects to a new chat."""
    if chat_id in chat_sessions:
        del chat_sessions[chat_id]
        if chat_id in chat_titles:
            del chat_titles[chat_id]
        if chat_id in chat_timestamps:
            del chat_timestamps[chat_id]
            
        # Determine the redirect URL
        remaining_chats = get_recent_chats()
        if remaining_chats:
            # Redirect to the newest remaining chat
            redirect_url = url_for('chat_view', chat_id=remaining_chats[0]['id'])
        else:
            # Redirect to a brand new chat
            redirect_url = url_for('new_chat')

        return jsonify({'success': True, 'redirect_url': redirect_url})
    
    return jsonify({'success': False, 'error': 'Chat not found'}), 404

# --- Run App ---
if __name__ == '__main__':
    # Add a mock chat for testing history functionality
    mock_id = generate_chat_id()
    chat_titles[mock_id] = "My Daily Workout Plan"
    chat_timestamps[mock_id] = time.time() - 3600 # 1 hour ago
    chat_sessions[mock_id] = [
        types.Content(role="user", parts=[types.Part.from_text("Can you create a 30-minute workout plan for me?")]),
        types.Content(role="model", parts=[types.Part.from_text("Here is a suggested plan...")]
    )]

    app.run(debug=True, host='0.0.0.0', port=os.environ.get('PORT', 5000))