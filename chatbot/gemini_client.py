import google.generativeai as genai
from django.conf import settings

# Configure Gemini
genai.configure(api_key=settings.GOOGLE_API_KEY)

MODEL_NAME = "gemini-2.5-flash"  # or "gemini-pro"

def send_to_gemini(history, user_message):
    """
    Sends `user_message` to Gemini along with prior history,
    prefixing the system prompt only on the very first turn.
    """

    # 1) Map your stored history into Gemini’s accepted roles:
    formatted_history = []
    for item in history:
        role = "user" if item["author"] == "user" else None
        if item["author"] == "assistant":
            role = "model"
        if role:
            formatted_history.append({
                "role": role,
                "parts": [item["content"]],
            })

    # 2) Initialize the model
    model = genai.GenerativeModel(MODEL_NAME)

    # 3) Start the chat with any existing history
    chat = model.start_chat(history=formatted_history)

    # 4) If this is the very first message (no prior history), 
    #    prefix your system prompt to orient Gemini.
    if not formatted_history:
        # Combine system prompt + user_message into one first prompt
        first_prompt = settings.CHAT_SYSTEM_PROMPT.strip() + "\n\n" + user_message
        response = chat.send_message(first_prompt)
    else:
        # Just send the user’s message as normal
        response = chat.send_message(user_message)

    # 5) Return the assistant's reply text
    return response.text
