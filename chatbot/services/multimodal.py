# ai_chatbot/services/multimodal.py
import os
import io
import logging
import asyncio
import tempfile
import base64
from typing import Dict, List, Any, Optional, Union, BinaryIO
from datetime import datetime
import speech_recognition as sr
from pydub import AudioSegment
from pydub.utils import which
from gtts import gTTS
from PIL import Image, ImageEnhance, ImageFilter
import requests
from django.core.files.uploadedfile import UploadedFile, InMemoryUploadedFile
from django.core.files.storage import default_storage
from django.conf import settings
from django.core.cache import cache
import cloudinary.uploader
import json

logger = logging.getLogger(__name__)


class MultimodalProcessor:
    """
    Advanced multimodal processing service for handling images, voice, and text
    Integrates with Gemini AI for image analysis and speech processing
    """
    
    def __init__(self):
        # Initialize speech recognizer
        self.recognizer = sr.Recognizer()
        
        # Supported formats
        self.supported_image_formats = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
        self.supported_audio_formats = ['mp3', 'wav', 'ogg', 'webm', 'm4a', 'flac']
        
        # Processing limits
        self.max_image_size = 10 * 1024 * 1024  # 10MB
        self.max_audio_duration = 300  # 5 minutes
        self.max_audio_size = 25 * 1024 * 1024  # 25MB
        
        # Cache settings
        self.cache_timeout = 1800  # 30 minutes
        
        # Speech recognition settings
        self.speech_languages = {
            'en': 'en-US',
            'fr': 'fr-FR',
            'es': 'es-ES',
            'de': 'de-DE',
            'pt': 'pt-BR',
            'it': 'it-IT',
            'zh': 'zh-CN',
            'ja': 'ja-JP',
            'ko': 'ko-KR'
        }
        
        # Text-to-speech settings
        self.tts_languages = {
            'en': 'en',
            'fr': 'fr',
            'es': 'es',
            'de': 'de',
            'pt': 'pt',
            'it': 'it',
            'zh': 'zh-cn',
            'ja': 'ja',
            'ko': 'ko'
        }
        
        # Cloudinary settings
        self.use_cloudinary = hasattr(settings, 'CLOUDINARY_CLOUD_NAME')
    
    async def process_image(
        self, 
        image_data: Union[UploadedFile, bytes, str], 
        user_message: str = "",
        analysis_type: str = "product_search"
    ) -> Dict[str, Any]:
        """
        Process uploaded image and extract information
        
        Args:
            image_data: Image file, bytes, or base64 string
            user_message: User's message about the image
            analysis_type: Type of analysis (product_search, general, comparison)
            
        Returns:
            Dict containing image analysis results
        """
        try:
            start_time = datetime.now()
            
            # Validate and preprocess image
            processed_image = await self._preprocess_image(image_data)
            if not processed_image:
                return {
                    'success': False,
                    'error': 'Invalid image format or size too large',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Upload to Cloudinary for storage
            image_url = None
            if self.use_cloudinary:
                try:
                    upload_result = await self._upload_to_cloudinary(processed_image['data'], 'chat_images')
                    image_url = upload_result.get('secure_url')
                except Exception as upload_error:
                    logger.warning(f"Failed to upload to Cloudinary: {str(upload_error)}")
            
            # Analyze image with Gemini (this will be called from the main service)
            gemini_analysis = {
                'image_data': processed_image['base64'],
                'user_message': user_message,
                'analysis_type': analysis_type
            }
            
            # Extract basic image information
            image_info = {
                'width': processed_image['width'],
                'height': processed_image['height'],
                'format': processed_image['format'],
                'size_mb': processed_image['size_mb'],
                'has_transparency': processed_image.get('has_transparency', False)
            }
            
            # Perform OCR if text detection is needed
            ocr_text = ""
            if analysis_type in ['product_search', 'text_extraction']:
                ocr_text = await self._extract_text_from_image(processed_image['pil_image'])
            
            # Detect colors and basic features
            image_features = await self._analyze_image_features(processed_image['pil_image'])
            
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            result = {
                'success': True,
                'image_info': image_info,
                'image_url': image_url,
                'ocr_text': ocr_text,
                'image_features': image_features,
                'gemini_analysis': gemini_analysis,  # Will be processed by the main service
                'processing_time': processing_time,
                'timestamp': datetime.now().isoformat(),
                'analysis_type': analysis_type
            }
            
            logger.info(f"Image processed successfully in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def process_voice_note(
        self, 
        audio_data: Union[UploadedFile, bytes], 
        language: str = 'en'
    ) -> Dict[str, Any]:
        """
        Process voice note and convert to text
        
        Args:
            audio_data: Audio file or bytes
            language: Language code for speech recognition
            
        Returns:
            Dict containing transcription and audio info
        """
        try:
            start_time = datetime.now()
            
            # Validate and preprocess audio
            processed_audio = await self._preprocess_audio(audio_data)
            if not processed_audio:
                return {
                    'success': False,
                    'error': 'Invalid audio format or size too large',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Upload to Cloudinary for storage
            audio_url = None
            if self.use_cloudinary:
                try:
                    upload_result = await self._upload_to_cloudinary(
                        processed_audio['data'], 
                        'chat_audio',
                        resource_type='auto'
                    )
                    audio_url = upload_result.get('secure_url')
                except Exception as upload_error:
                    logger.warning(f"Failed to upload audio to Cloudinary: {str(upload_error)}")
            
            # Convert speech to text
            transcription = await self._speech_to_text(
                processed_audio['audio_segment'], 
                language
            )
            
            # Extract audio features
            audio_info = {
                'duration_seconds': processed_audio['duration'],
                'format': processed_audio['format'],
                'sample_rate': processed_audio.get('sample_rate', 0),
                'channels': processed_audio.get('channels', 0),
                'size_mb': processed_audio['size_mb']
            }
            
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            result = {
                'success': True,
                'transcription': transcription,
                'confidence': transcription.get('confidence', 0.0),
                'audio_info': audio_info,
                'audio_url': audio_url,
                'language_detected': transcription.get('language', language),
                'processing_time': processing_time,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"Voice note processed successfully in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error processing voice note: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def generate_speech(
        self, 
        text: str, 
        language: str = 'en',
        speed: float = 1.0
    ) -> Dict[str, Any]:
        """
        Convert text to speech
        
        Args:
            text: Text to convert to speech
            language: Language code
            speed: Speech speed (0.5 to 2.0)
            
        Returns:
            Dict containing audio data and metadata
        """
        try:
            if not text or len(text.strip()) == 0:
                return {
                    'success': False,
                    'error': 'No text provided',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Limit text length
            if len(text) > 1000:
                text = text[:1000] + "..."
            
            start_time = datetime.now()
            
            # Get language code for TTS
            tts_lang = self.tts_languages.get(language, 'en')
            
            # Generate speech using gTTS
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                try:
                    tts = gTTS(text=text, lang=tts_lang, slow=False)
                    tts.save(temp_file.name)
                    
                    # Read the generated audio
                    with open(temp_file.name, 'rb') as audio_file:
                        audio_data = audio_file.read()
                    
                    # Adjust speed if needed
                    if speed != 1.0:
                        audio_data = await self._adjust_audio_speed(audio_data, speed)
                    
                    # Upload to Cloudinary
                    audio_url = None
                    if self.use_cloudinary:
                        try:
                            upload_result = await self._upload_to_cloudinary(
                                audio_data, 
                                'generated_speech',
                                resource_type='auto'
                            )
                            audio_url = upload_result.get('secure_url')
                        except Exception as upload_error:
                            logger.warning(f"Failed to upload generated speech: {str(upload_error)}")
                    
                    end_time = datetime.now()
                    processing_time = (end_time - start_time).total_seconds()
                    
                    result = {
                        'success': True,
                        'audio_data': base64.b64encode(audio_data).decode('utf-8'),
                        'audio_url': audio_url,
                        'text': text,
                        'language': tts_lang,
                        'speed': speed,
                        'duration_estimate': len(text) / 15,  # Rough estimate: ~15 chars per second
                        'processing_time': processing_time,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    logger.info(f"Speech generated successfully in {processing_time:.2f}s")
                    return result
                
                finally:
                    # Clean up temp file
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
            
        except Exception as e:
            logger.error(f"Error generating speech: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _preprocess_image(self, image_data: Union[UploadedFile, bytes, str]) -> Optional[Dict[str, Any]]:
        """Preprocess and validate image"""
        try:
            pil_image = None
            original_data = None
            
            # Handle different input types
            if isinstance(image_data, UploadedFile):
                original_data = image_data.read()
                pil_image = Image.open(io.BytesIO(original_data))
            elif isinstance(image_data, bytes):
                original_data = image_data
                pil_image = Image.open(io.BytesIO(original_data))
            elif isinstance(image_data, str):
                # Assume base64 encoded
                if image_data.startswith('data:image'):
                    image_data = image_data.split(',')[1]
                original_data = base64.b64decode(image_data)
                pil_image = Image.open(io.BytesIO(original_data))
            else:
                return None
            
            # Check file size
            if len(original_data) > self.max_image_size:
                return None
            
            # Get image info
            width, height = pil_image.size
            image_format = pil_image.format.lower() if pil_image.format else 'unknown'
            
            # Check if format is supported
            if image_format not in self.supported_image_formats:
                return None
            
            # Convert to RGB if necessary
            if pil_image.mode not in ('RGB', 'L'):
                pil_image = pil_image.convert('RGB')
            
            # Resize if too large (keep aspect ratio)
            max_dimension = 1024
            if width > max_dimension or height > max_dimension:
                pil_image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                width, height = pil_image.size
                
                # Convert back to bytes
                output = io.BytesIO()
                pil_image.save(output, format='JPEG', quality=85)
                original_data = output.getvalue()
            
            # Convert to base64
            base64_data = base64.b64encode(original_data).decode('utf-8')
            
            return {
                'pil_image': pil_image,
                'data': original_data,
                'base64': base64_data,
                'width': width,
                'height': height,
                'format': image_format,
                'size_mb': len(original_data) / (1024 * 1024),
                'has_transparency': pil_image.mode in ('RGBA', 'LA') or 'transparency' in pil_image.info
            }
            
        except Exception as e:
            logger.error(f"Error preprocessing image: {str(e)}")
            return None
    
    async def _preprocess_audio(self, audio_data: Union[UploadedFile, bytes]) -> Optional[Dict[str, Any]]:
        """Preprocess and validate audio"""
        try:
            original_data = None
            
            # Handle different input types
            if isinstance(audio_data, UploadedFile):
                original_data = audio_data.read()
            elif isinstance(audio_data, bytes):
                original_data = audio_data
            else:
                return None
            
            # Check file size
            if len(original_data) > self.max_audio_size:
                return None
            
            # Load audio with pydub
            audio_segment = AudioSegment.from_file(io.BytesIO(original_data))
            
            # Check duration
            duration_seconds = len(audio_segment) / 1000.0
            if duration_seconds > self.max_audio_duration:
                return None
            
            # Convert to WAV for speech recognition (in memory)
            wav_data = io.BytesIO()
            audio_segment.export(wav_data, format='wav')
            wav_bytes = wav_data.getvalue()
            
            return {
                'audio_segment': audio_segment,
                'data': original_data,
                'wav_data': wav_bytes,
                'duration': duration_seconds,
                'format': 'wav',  # Converted format
                'sample_rate': audio_segment.frame_rate,
                'channels': audio_segment.channels,
                'size_mb': len(original_data) / (1024 * 1024)
            }
            
        except Exception as e:
            logger.error(f"Error preprocessing audio: {str(e)}")
            return None
    
    async def _extract_text_from_image(self, pil_image: Image.Image) -> str:
        """Extract text from image using OCR"""
        try:
            # Basic OCR using PIL and simple pattern matching
            # For production, consider using pytesseract or Google Vision API
            
            # Enhance image for better OCR
            enhanced_image = pil_image.copy()
            
            # Convert to grayscale
            if enhanced_image.mode != 'L':
                enhanced_image = enhanced_image.convert('L')
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(enhanced_image)
            enhanced_image = enhancer.enhance(2.0)
            
            # Apply sharpening filter
            enhanced_image = enhanced_image.filter(ImageFilter.SHARPEN)
            
            # For now, return empty string - implement actual OCR if needed
            # You can integrate pytesseract here:
            # import pytesseract
            # return pytesseract.image_to_string(enhanced_image)
            
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting text from image: {str(e)}")
            return ""
    
    async def _analyze_image_features(self, pil_image: Image.Image) -> Dict[str, Any]:
        """Analyze basic image features"""
        try:
            features = {}
            
            # Get dominant colors
            # Convert to RGB and resize for faster processing
            rgb_image = pil_image.convert('RGB')
            rgb_image.thumbnail((100, 100), Image.Resampling.LANCZOS)
            
            # Get color histogram
            colors = rgb_image.getcolors(maxcolors=256*256*256)
            if colors:
                # Sort by frequency and get top colors
                colors.sort(key=lambda x: x[0], reverse=True)
                top_colors = []
                for count, color in colors[:5]:
                    top_colors.append({
                        'color': f"rgb({color[0]}, {color[1]}, {color[2]})",
                        'frequency': count
                    })
                features['dominant_colors'] = top_colors
            
            # Calculate average brightness
            grayscale = pil_image.convert('L')
            histogram = grayscale.histogram()
            pixels = sum(histogram)
            brightness = sum(i * histogram[i] for i in range(256)) / pixels if pixels > 0 else 0
            features['brightness'] = round(brightness / 255 * 100, 2)  # Convert to percentage
            
            # Determine if image is likely a product photo
            aspect_ratio = pil_image.width / pil_image.height
            features['aspect_ratio'] = round(aspect_ratio, 2)
            
            # Simple heuristics for product detection
            is_square_ish = 0.8 <= aspect_ratio <= 1.2
            is_bright_enough = brightness > 50
            features['likely_product_photo'] = is_square_ish and is_bright_enough
            
            return features
            
        except Exception as e:
            logger.error(f"Error analyzing image features: {str(e)}")
            return {}
    
    async def _speech_to_text(self, audio_segment: AudioSegment, language: str = 'en') -> Dict[str, Any]:
        """Convert speech to text"""
        try:
            # Get language code for speech recognition
            recognition_lang = self.speech_languages.get(language, 'en-US')
            
            # Convert AudioSegment to wav bytes
            wav_io = io.BytesIO()
            audio_segment.export(wav_io, format='wav')
            wav_io.seek(0)
            
            # Use speech recognition
            with sr.AudioFile(wav_io) as source:
                # Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.record(source)
            
            # Try Google Speech Recognition first
            try:
                text = self.recognizer.recognize_google(audio, language=recognition_lang)
                return {
                    'text': text,
                    'confidence': 0.8,  # Google doesn't provide confidence scores
                    'language': language,
                    'engine': 'google'
                }
            except sr.UnknownValueError:
                logger.info("Google Speech Recognition could not understand audio")
            except sr.RequestError as e:
                logger.error(f"Could not request results from Google Speech Recognition: {e}")
            
            # Fallback to offline recognition
            try:
                text = self.recognizer.recognize_sphinx(audio)
                return {
                    'text': text,
                    'confidence': 0.6,  # Lower confidence for offline recognition
                    'language': language,
                    'engine': 'sphinx'
                }
            except sr.UnknownValueError:
                logger.info("Sphinx could not understand audio")
            except sr.RequestError as e:
                logger.error(f"Sphinx error: {e}")
            
            # If all methods fail
            return {
                'text': "",
                'confidence': 0.0,
                'language': language,
                'engine': 'none',
                'error': "Could not transcribe audio"
            }
            
        except Exception as e:
            logger.error(f"Error in speech to text: {str(e)}")
            return {
                'text': "",
                'confidence': 0.0,
                'language': language,
                'error': str(e)
            }
    
    async def _adjust_audio_speed(self, audio_data: bytes, speed: float) -> bytes:
        """Adjust audio playback speed"""
        try:
            # Load audio from bytes
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))
            
            # Adjust speed (speed > 1.0 = faster, speed < 1.0 = slower)
            if speed != 1.0:
                # Change frame rate to adjust speed
                new_frame_rate = int(audio_segment.frame_rate * speed)
                adjusted_audio = audio_segment._spawn(audio_segment.raw_data, overrides={
                    "frame_rate": new_frame_rate
                }).set_frame_rate(audio_segment.frame_rate)
            else:
                adjusted_audio = audio_segment
            
            # Export back to bytes
            output = io.BytesIO()
            adjusted_audio.export(output, format='mp3')
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Error adjusting audio speed: {str(e)}")
            return audio_data  # Return original if adjustment fails
    
    async def _upload_to_cloudinary(
        self, 
        data: bytes, 
        folder: str,
        resource_type: str = 'image'
    ) -> Dict[str, Any]:
        """Upload data to Cloudinary"""
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(data)
                temp_file.flush()
                
                # Upload to Cloudinary
                result = await asyncio.to_thread(
                    cloudinary.uploader.upload,
                    temp_file.name,
                    folder=folder,
                    resource_type=resource_type
                )
                
                return result
                
        except Exception as e:
            logger.error(f"Error uploading to Cloudinary: {str(e)}")
            raise e
    
    def get_supported_formats(self) -> Dict[str, List[str]]:
        """Get supported file formats"""
        return {
            'images': self.supported_image_formats,
            'audio': self.supported_audio_formats
        }
    
    def get_supported_languages(self) -> Dict[str, Dict[str, str]]:
        """Get supported languages for speech processing"""
        return {
            'speech_recognition': self.speech_languages,
            'text_to_speech': self.tts_languages
        }
    
    async def validate_file(
        self, 
        file_data: Union[UploadedFile, bytes], 
        file_type: str
    ) -> Dict[str, Any]:
        """Validate uploaded file"""
        try:
            if file_type == 'image':
                processed = await self._preprocess_image(file_data)
                if processed:
                    return {
                        'valid': True,
                        'file_type': 'image',
                        'format': processed['format'],
                        'size_mb': processed['size_mb'],
                        'dimensions': f"{processed['width']}x{processed['height']}"
                    }
            elif file_type == 'audio':
                processed = await self._preprocess_audio(file_data)
                if processed:
                    return {
                        'valid': True,
                        'file_type': 'audio',
                        'format': processed['format'],
                        'size_mb': processed['size_mb'],
                        'duration': f"{processed['duration']:.2f}s"
                    }
            
            return {
                'valid': False,
                'error': f'Invalid or unsupported {file_type} file'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e)
            }


# Helper functions
def is_image_file(filename: str) -> bool:
    """Check if filename is an image file"""
    if not filename:
        return False
    
    extension = filename.lower().split('.')[-1]
    return extension in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']


def is_audio_file(filename: str) -> bool:
    """Check if filename is an audio file"""
    if not filename:
        return False
    
    extension = filename.lower().split('.')[-1]
    return extension in ['mp3', 'wav', 'ogg', 'webm', 'm4a', 'flac', 'aac']


def get_file_type_from_content(data: bytes) -> str:
    """Detect file type from content"""
    # Simple magic number detection
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    elif data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    elif data.startswith(b'GIF8'):
        return 'image/gif'
    elif data.startswith(b'ID3') or data.startswith(b'\xff\xfb'):
        return 'audio/mp3'
    elif data.startswith(b'RIFF') and b'WAVE' in data[:12]:
        return 'audio/wav'
    else:
        return 'unknown'


async def compress_image(pil_image: Image.Image, max_size_kb: int = 500) -> Image.Image:
    """Compress image to target size"""
    output = io.BytesIO()
    
    # Start with high quality
    quality = 95
    
    while quality > 10:
        output.seek(0)
        output.truncate(0)
        
        pil_image.save(output, format='JPEG', quality=quality)
        
        if len(output.getvalue()) <= max_size_kb * 1024:
            break
        
        quality -= 10
    
    output.seek(0)
    return Image.open(output)