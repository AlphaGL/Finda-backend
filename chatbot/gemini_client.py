# gemini_client.py - FULLY ENHANCED & BUG-FIXED VERSION
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
import logging
from io import BytesIO
import time

logger = logging.getLogger(__name__)

# Configure Gemini with error handling
try:
    genai.configure(api_key=settings.GOOGLE_API_KEY)
    MODEL_NAME = "gemini-2.0-flash-exp"  # Updated for vision and audio support
except Exception as config_error:
    logger.error(f"Gemini configuration error: {str(config_error)}")
    MODEL_NAME = "gemini-pro"  # Fallback model


def send_to_gemini(history, user_message, max_retries=3):
    """
    ENHANCED: Sends user_message to Gemini with comprehensive error handling and retries
    """
    for attempt in range(max_retries):
        try:
            if not user_message or len(user_message.strip()) < 1:
                return "I'd be happy to help! What would you like to know about Finda?"
            
            # Validate and clean history
            formatted_history = []
            if history and isinstance(history, list):
                for item in history[-10:]:  # Limit to last 10 messages
                    try:
                        if isinstance(item, dict) and 'author' in item and 'content' in item:
                            role = "user" if item["author"] == "user" else "model"
                            if item["author"] == "assistant":
                                role = "model"
                            
                            if role and item['content']:
                                formatted_history.append({
                                    "role": role,
                                    "parts": [str(item["content"])[:2000]],  # Limit content length
                                })
                    except Exception as item_error:
                        logger.error(f"History item error: {str(item_error)}")
                        continue
            
            # Initialize the model
            model = genai.GenerativeModel(MODEL_NAME)
            
            # Start the chat with any existing history
            chat = model.start_chat(history=formatted_history)
            
            # If this is the very first message (no prior history), 
            # prefix your system prompt to orient Gemini.
            if not formatted_history:
                # Get system prompt from settings
                system_prompt = getattr(settings, 'CHAT_SYSTEM_PROMPT', 
                    "You are Finda's helpful shopping assistant. Help users find products and services on Finda marketplace.")
                
                first_prompt = system_prompt.strip() + "\n\nUser: " + str(user_message)
                response = chat.send_message(first_prompt)
            else:
                # Just send the user's message as normal
                response = chat.send_message(str(user_message))
            
            # Validate response
            if response and hasattr(response, 'text') and response.text:
                response_text = response.text.strip()
                
                # Check for appropriate response length
                if len(response_text) < 10:
                    return "I'm here to help you find what you need on Finda! What are you looking for?"
                
                # Limit response length
                if len(response_text) > 3000:
                    response_text = response_text[:2800] + "...\n\nWhat else can I help you find?"
                
                return response_text
            else:
                raise Exception("Empty or invalid response from Gemini")
                
        except Exception as e:
            logger.error(f"Gemini API error (attempt {attempt + 1}): {str(e)}")
            
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                # Final fallback response
                return (
                    "I'm having a small technical issue connecting to my AI brain right now. 🔧\n\n"
                    "But I can still help you! Try:\n"
                    "• Searching for specific items (e.g., 'iPhone', 'laptop')\n"
                    "• Browsing categories (say 'categories')\n"
                    "• Asking about Finda's features\n\n"
                    "What are you looking for today?"
                )
    
    # This should never be reached, but just in case
    return "I'm here to help! What can I find for you on Finda?"


def analyze_image_with_gemini(image_file, user_query="What products are in this image?", max_retries=2):
    """
    ENHANCED: Analyze uploaded image using Gemini Vision with comprehensive error handling
    """
    for attempt in range(max_retries):
        try:
            if not image_file:
                return "No image provided. Please upload an image and I'll help you find similar items on Finda!"
            
            logger.info(f"Analyzing image (attempt {attempt + 1})")
            
            # Initialize the model
            model = genai.GenerativeModel(MODEL_NAME)
            
            # Process image safely
            try:
                # Handle different image file types
                if hasattr(image_file, 'read'):
                    # It's a file-like object
                    image_file.seek(0)  # Reset file pointer
                    img = Image.open(image_file)
                else:
                    # It's a file path
                    img = Image.open(image_file)
                
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize if too large (to prevent API limits)
                max_size = 1024
                if img.width > max_size or img.height > max_size:
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
            except Exception as img_error:
                logger.error(f"Image processing error: {str(img_error)}")
                return f"I can see you sent an image, but I'm having trouble processing it. Please try uploading a clearer image or describe what you're looking for instead."
            
            # Create enhanced prompt for better product identification
            prompt = f"""
You are Finda, a shopping assistant. Analyze this image to help the user find products on our marketplace.

Focus on identifying:
- Specific product types and categories
- Brand names or logos (if clearly visible)
- Colors, styles, and distinctive features
- Material type or fabric (if applicable)
- Estimated size or dimensions
- Product condition (new/used)
- Price range estimates (in Nigerian Naira if possible)

User query: {user_query}

Provide a helpful response that includes:
1. A clear description of what you see in the image
2. Specific search terms that would work well on Finda
3. Relevant product categories to explore
4. Similar product suggestions

Be conversational and enthusiastic about helping them find exactly what they need on Finda's marketplace!

Response should be concise but informative (max 300 words).
"""
            
            # Generate content with image and prompt
            try:
                response = model.generate_content([prompt, img])
                
                if response and hasattr(response, 'text') and response.text:
                    analysis_text = response.text.strip()
                    
                    # Validate response quality
                    if len(analysis_text) < 20:
                        raise Exception("Response too short")
                    
                    # Ensure it's not just error text
                    error_indicators = ['sorry', 'cannot', 'unable', 'error', 'failed']
                    if all(indicator in analysis_text.lower() for indicator in error_indicators[:2]):
                        raise Exception("Analysis failed")
                    
                    return analysis_text
                else:
                    raise Exception("Empty response from vision model")
                    
            except Exception as generation_error:
                logger.error(f"Content generation error: {str(generation_error)}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    raise generation_error
                    
        except Exception as e:
            logger.error(f"Image analysis error (attempt {attempt + 1}): {str(e)}")
            
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
    
    # Final fallback
    return (
        "I can see your image, but I'm having trouble analyzing it in detail right now. "
        "Could you describe what you're looking for instead? For example:\n"
        "• 'Red Nike shoes'\n"
        "• 'Samsung smartphone'\n"
        "• 'Wooden dining table'\n\n"
        "I'll help you find exactly what you need on Finda!"
    )


def transcribe_audio(audio_file, max_retries=2):
    """
    ENHANCED: Convert audio file to text using speech recognition with comprehensive error handling
    """
    temp_file_path = None
    
    for attempt in range(max_retries):
        try:
            if not audio_file:
                return None
            
            logger.info(f"Transcribing audio (attempt {attempt + 1})")
            
            recognizer = sr.Recognizer()
            
            # Create temporary file with proper cleanup
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
                temp_file_path = temp_file.name
                
                try:
                    # Reset file pointer if it's a file-like object
                    if hasattr(audio_file, 'seek'):
                        audio_file.seek(0)
                    
                    # Convert to WAV format for better compatibility
                    audio = AudioSegment.from_file(audio_file)
                    
                    # Normalize audio
                    audio = audio.normalize()
                    
                    # Ensure proper format
                    audio = audio.set_frame_rate(16000).set_channels(1)
                    
                    # Export to temporary file
                    audio.export(temp_file.name, format="wav")
                    
                except Exception as audio_error:
                    logger.error(f"Audio conversion error: {str(audio_error)}")
                    if attempt < max_retries - 1:
                        continue
                    else:
                        return None
                
                # Transcribe with multiple language attempts for Nigeria
                languages_to_try = [
                    'en-NG',  # Nigerian English
                    'en-US',  # US English
                    'en-GB',  # British English
                    'en'      # Generic English
                ]
                
                transcript = None
                
                for lang in languages_to_try:
                    try:
                        with sr.AudioFile(temp_file.name) as source:
                            # Adjust for ambient noise
                            recognizer.adjust_for_ambient_noise(source, duration=0.5)
                            
                            # Record audio data
                            audio_data = recognizer.record(source)
                            
                            # Recognize speech
                            transcript = recognizer.recognize_google(
                                audio_data, 
                                language=lang,
                                show_all=False
                            )
                            
                            if transcript and len(transcript.strip()) > 0:
                                logger.info(f"Successfully transcribed with language: {lang}")
                                break
                                
                    except sr.UnknownValueError:
                        # Speech was unintelligible
                        continue
                    except sr.RequestError as e:
                        logger.error(f"Speech recognition request error with {lang}: {str(e)}")
                        continue
                    except Exception as recog_error:
                        logger.error(f"Recognition error with {lang}: {str(recog_error)}")
                        continue
                
                # Clean up temporary file
                try:
                    if temp_file_path and os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                        temp_file_path = None
                except Exception as cleanup_error:
                    logger.error(f"Temp file cleanup error: {str(cleanup_error)}")
                
                if transcript and len(transcript.strip()) > 0:
                    # Clean and validate transcript
                    transcript = transcript.strip()
                    
                    # Basic validation
                    if len(transcript) > 500:
                        transcript = transcript[:500] + "..."
                    
                    return transcript
                else:
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    
        except Exception as e:
            logger.error(f"Transcription error (attempt {attempt + 1}): {str(e)}")
            
            # Clean up temp file on error
            try:
                if temp_file_path and os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
            except:
                pass
            
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
    
    # Final cleanup
    try:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
    except:
        pass
    
    return None


def generate_voice_response(text_response, language='en', slow=False, max_retries=2):
    """
    ENHANCED: Convert bot response to speech with comprehensive error handling
    """
    for attempt in range(max_retries):
        temp_file_path = None
        try:
            if not text_response or len(text_response.strip()) < 1:
                return None
            
            logger.info(f"Generating voice response (attempt {attempt + 1})")
            
            # Clean text for TTS
            clean_text = clean_text_for_speech(text_response)
            
            if len(clean_text) < 5:
                clean_text = "I found some options for you on Finda!"
            
            # Create TTS object
            try:
                tts = gTTS(text=clean_text, lang=language, slow=slow)
            except Exception as tts_error:
                logger.error(f"TTS creation error: {str(tts_error)}")
                if language != 'en':
                    # Fallback to English
                    tts = gTTS(text=clean_text, lang='en', slow=slow)
                else:
                    if attempt < max_retries - 1:
                        continue
                    else:
                        return None
            
            # Generate unique filename
            file_name = f"voice_responses/{uuid.uuid4()}.mp3"
            
            # Save as temporary file first
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                temp_file_path = temp_file.name
                
                try:
                    tts.save(temp_file.name)
                except Exception as save_error:
                    logger.error(f"TTS save error: {str(save_error)}")
                    if attempt < max_retries - 1:
                        continue
                    else:
                        return None
                
                # Verify file was created and has content
                if not os.path.exists(temp_file.name) or os.path.getsize(temp_file.name) == 0:
                    logger.error("Generated audio file is empty or doesn't exist")
                    if attempt < max_retries - 1:
                        continue
                    else:
                        return None
                
                # Upload to your storage system
                try:
                    with open(temp_file.name, 'rb') as audio_file:
                        saved_path = default_storage.save(file_name, audio_file)
                    
                    # Get public URL
                    url = default_storage.url(saved_path)
                    
                    # Clean up temp file
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
                    
                    logger.info(f"Voice response generated successfully: {url}")
                    return url
                    
                except Exception as upload_error:
                    logger.error(f"Audio upload error: {str(upload_error)}")
                    if attempt < max_retries - 1:
                        continue
                    else:
                        return None
                        
        except Exception as e:
            logger.error(f"Voice generation error (attempt {attempt + 1}): {str(e)}")
            
            # Clean up temp file on error
            try:
                if temp_file_path and os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
            except:
                pass
            
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
    
    return None


def clean_text_for_speech(text):
    """
    ENHANCED: Clean text specifically for speech synthesis
    """
    try:
        import re
        
        if not text:
            return ""
        
        # Remove markdown formatting
        cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
        cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)    # Italic
        cleaned = re.sub(r'#{1,6}\s', '', cleaned)          # Headers
        cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)  # Links
        
        # Remove URLs
        cleaned = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', cleaned)
        
        # Remove emojis for better speech (keep some as words)
        emoji_replacements = {
            '🛍️': 'shopping',
            '📸': 'image',
            '🎤': 'voice',
            '💰': 'price',
            '📍': 'location',
            '⭐': 'star',
            '🔍': 'search',
            '💡': 'tip',
            '✅': 'check',
            '🚚': 'delivery',
            '💬': '',
            '🏠': 'local',
            '💯': 'verified',
            '📦': 'item',
            '⚖️': 'compare',
            '🔄': '',
            '🔧': 'technical',
            '📊': 'results'
        }
        
        for emoji, replacement in emoji_replacements.items():
            cleaned = cleaned.replace(emoji, replacement)
        
        # Remove remaining emojis
        cleaned = re.sub(r'[^\w\s.,!?;:()\-"]', '', cleaned)
        
        # Convert common symbols to words
        replacements = {
            '&': 'and',
            '@': 'at',
            '#': 'number',
            '%': 'percent',
            '₦': 'naira',
            ':':'dollars',
            '€': 'euros',
            '£': 'pounds'
        }
        
        for symbol, word in replacements.items():
            cleaned = cleaned.replace(symbol, word)
        
        # Clean up bullet points and numbers
        cleaned = re.sub(r'^\s*[•·▪▫‣⁃]\s*', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'^\s*\d+[.)]\s*', '', cleaned, flags=re.MULTILINE)
        
        # Clean up extra whitespace
        cleaned = ' '.join(cleaned.split())
        
        # Limit length for TTS (most services have limits)
        if len(cleaned) > 400:
            sentences = cleaned.split('.')
            result = ""
            for sentence in sentences:
                if len(result + sentence) < 350:
                    result += sentence + ". "
                else:
                    break
            cleaned = result.strip()
            
            # If still too long, cut at word boundary
            if len(cleaned) > 400:
                words = cleaned.split()
                truncated = []
                char_count = 0
                for word in words:
                    if char_count + len(word) < 380:
                        truncated.append(word)
                        char_count += len(word) + 1
                    else:
                        break
                cleaned = ' '.join(truncated)
        
        # Ensure it ends properly
        if cleaned and not cleaned.endswith(('.', '!', '?')):
            cleaned += '.'
        
        return cleaned
        
    except Exception as e:
        logger.error(f"Text cleaning error: {str(e)}")
        # Return a safe fallback
        return str(text)[:200] if text else "I found some options for you."


def test_gemini_connection():
    """
    ENHANCED: Test Gemini API connection
    """
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content("Hello")
        
        if response and hasattr(response, 'text') and response.text:
            logger.info("Gemini connection test successful")
            return True, "Connection successful"
        else:
            logger.error("Gemini connection test failed - no response")
            return False, "No response from API"
            
    except Exception as e:
        logger.error(f"Gemini connection test failed: {str(e)}")
        return False, str(e)


def validate_api_key():
    """
    ENHANCED: Validate Google API key configuration
    """
    try:
        api_key = getattr(settings, 'GOOGLE_API_KEY', None)
        
        if not api_key:
            return False, "GOOGLE_API_KEY not configured"
        
        if len(api_key) < 20:
            return False, "GOOGLE_API_KEY appears to be invalid"
        
        # Test the key with a simple request
        success, message = test_gemini_connection()
        return success, message
        
    except Exception as e:
        logger.error(f"API key validation error: {str(e)}")
        return False, str(e)


# Fallback responses for when AI is unavailable
FALLBACK_RESPONSES = {
    'search': "I can help you search Finda! Try searching for specific items like 'iPhone', 'laptop', or 'plumber'.",
    'greeting': "Welcome to Finda! I'm here to help you find amazing products and services. What are you looking for?",
    'categories': "Browse our categories: Electronics, Fashion, Home & Garden, Automotive, Services, and more!",
    'help': "I can help you find products and services on Finda! Try searching for what you need or say 'categories' to browse.",
    'default': "I'm here to help you shop on Finda! What can I find for you today?"
}


def get_fallback_response(intent='default'):
    """
    ENHANCED: Get appropriate fallback response when AI is unavailable
    """
    return FALLBACK_RESPONSES.get(intent, FALLBACK_RESPONSES['default'])


# Export main functions
__all__ = [
    'send_to_gemini',
    'analyze_image_with_gemini',
    'transcribe_audio',
    'generate_voice_response',
    'clean_text_for_speech',
    'test_gemini_connection',
    'validate_api_key',
    'get_fallback_response'
]