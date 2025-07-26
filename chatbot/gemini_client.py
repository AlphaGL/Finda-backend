# gemini_client.py - Enhanced with image and voice support
import google.generativeai as genai
from django.conf import settings
from PIL import Image
import speech_recognition as sr
from pydub import AudioSegment
import tempfile
import os
from gtts import gTTS
import uuid
from django.core.files.storage import default_storage

# Configure Gemini
genai.configure(api_key=settings.GOOGLE_API_KEY)

MODEL_NAME = "gemini-2.0-flash-exp"  # Updated for vision and audio support

def send_to_gemini(history, user_message):
    """
    Sends `user_message` to Gemini along with prior history,
    prefixing the system prompt only on the very first turn.
    """
    # Map your stored history into Gemini's accepted roles:
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

    # Initialize the model
    model = genai.GenerativeModel(MODEL_NAME)

    # Start the chat with any existing history
    chat = model.start_chat(history=formatted_history)

    # If this is the very first message (no prior history), 
    # prefix your system prompt to orient Gemini.
    if not formatted_history:
        # Combine system prompt + user_message into one first prompt
        first_prompt = settings.CHAT_SYSTEM_PROMPT.strip() + "\n\n" + user_message
        response = chat.send_message(first_prompt)
    else:
        # Just send the user's message as normal
        response = chat.send_message(user_message)

    # Return the assistant's reply text
    return response.text

def analyze_image_with_gemini(image_file, user_query="What products are in this image?"):
    """
    Analyze uploaded image using Gemini Vision to identify products
    """
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        
        # Open and process image
        img = Image.open(image_file)
        
        prompt = f"""
        You are Finda, a shopping assistant. Analyze this image to help the user find products.
        
        Focus on identifying:
        - Product types and categories
        - Brand names (if visible)
        - Colors, styles, and key features
        - Price range estimates
        - Similar product suggestions
        
        User query: {user_query}
        
        Provide a helpful response that includes:
        1. What you see in the image
        2. Search terms that would help find similar items
        3. Product recommendations
        
        Be conversational and helpful, as if speaking directly to a shopper.
        """
        
        response = model.generate_content([prompt, img])
        return response.text
        
    except Exception as e:
        return f"I can see your image, but I'm having trouble analyzing it right now. Could you describe what you're looking for instead? Error: {str(e)}"

def transcribe_audio(audio_file):
    """
    Convert audio file to text using speech recognition
    """
    try:
        recognizer = sr.Recognizer()
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
            # Convert to WAV format for better compatibility
            audio = AudioSegment.from_file(audio_file)
            audio.export(temp_file.name, format="wav")
            
            # Transcribe with language support for Nigeria
            languages_to_try = ['en-US', 'en-NG', 'en-UK']
            
            for lang in languages_to_try:
                try:
                    with sr.AudioFile(temp_file.name) as source:
                        # Adjust for ambient noise
                        recognizer.adjust_for_ambient_noise(source)
                        audio_data = recognizer.record(source)
                        transcript = recognizer.recognize_google(audio_data, language=lang)
                        break
                except sr.UnknownValueError:
                    continue
            else:
                transcript = None
            
            # Cleanup
            os.unlink(temp_file.name)
            
        return transcript
        
    except Exception as e:
        print(f"Transcription error: {str(e)}")
        return None

def generate_voice_response(text_response, language='en', slow=False):
    """
    Convert bot response to speech and return URL
    """
    try:
        # Create TTS object
        tts = gTTS(text=text_response, lang=language, slow=slow)
        
        # Generate unique filename
        file_name = f"voice_responses/{uuid.uuid4()}.mp3"
        
        # Save as temporary file first
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
            tts.save(temp_file.name)
            
            # Upload to your storage system
            with open(temp_file.name, 'rb') as audio_file:
                saved_path = default_storage.save(file_name, audio_file)
            
            # Cleanup temp file
            os.unlink(temp_file.name)
        
        return default_storage.url(saved_path)
        
    except Exception as e:
        print(f"Voice generation error: {str(e)}")
        return None