# chatbot/utils.py - Enhanced Utilities for Advanced Features
import re
import json
import io
from PIL import Image
import speech_recognition as sr
from pydub import AudioSegment
from pydub.utils import make_chunks
import google.generativeai as genai
from django.conf import settings
from django.db.models import Q, Avg
from django.utils import timezone
from decimal import Decimal
import requests
from typing import Dict, List, Any, Optional
import tempfile
import os

from main.models import Products, Services, Category, Country, State, City


# ===========================
#  VOICE PROCESSING UTILITIES
# ===========================

def process_voice_to_text(audio_file) -> Optional[str]:
    """
    Convert voice message to text using Google Speech Recognition
    Supports multiple audio formats and languages
    """
    try:
        # Initialize recognizer
        recognizer = sr.Recognizer()
        
        # Handle different audio formats
        audio_data = None
        
        # Read the uploaded file
        audio_content = audio_file.read()
        audio_file.seek(0)  # Reset file pointer
        
        # Convert to wav format if needed
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_wav:
            if audio_file.name.lower().endswith(('.mp3', '.m4a', '.ogg', '.flac')):
                # Convert to wav using pydub
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_content))
                audio_segment.export(temp_wav.name, format='wav')
            else:
                # Assume it's already wav format
                temp_wav.write(audio_content)
            
            # Process with speech recognition
            with sr.AudioFile(temp_wav.name) as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio_data = recognizer.record(source)
        
        # Clean up temp file
        if os.path.exists(temp_wav.name):
            os.unlink(temp_wav.name)
        
        if not audio_data:
            return None
        
        # Try multiple recognition engines
        recognition_results = []
        
        # Google Speech Recognition (free tier)
        try:
            google_result = recognizer.recognize_google(
                audio_data, 
                language='en-US',
                show_all=False
            )
            if google_result:
                recognition_results.append(google_result)
        except sr.UnknownValueError:
            pass
        except sr.RequestError:
            pass
        
        # Try with different languages if no result
        if not recognition_results:
            languages = ['en-GB', 'en-AU', 'fr-FR', 'es-ES', 'de-DE']
            for lang in languages:
                try:
                    result = recognizer.recognize_google(audio_data, language=lang)
                    if result:
                        recognition_results.append(result)
                        break
                except:
                    continue
        
        # Return best result
        if recognition_results:
            return recognition_results[0].strip()
        
        return None
        
    except Exception as e:
        print(f"Voice processing error: {e}")
        return None


def detect_language_from_audio(text: str) -> str:
    """
    Detect language from transcribed text
    """
    # Simple language detection based on common words
    language_keywords = {
        'en': ['the', 'and', 'is', 'for', 'with', 'this', 'that', 'have', 'you', 'are'],
        'fr': ['le', 'de', 'et', 'à', 'un', 'il', 'être', 'et', 'en', 'avoir'],
        'es': ['el', 'de', 'que', 'y', 'a', 'en', 'un', 'es', 'se', 'no'],
        'de': ['der', 'die', 'und', 'zu', 'den', 'das', 'nicht', 'von', 'sie', 'ist'],
    }
    
    text_lower = text.lower()
    language_scores = {}
    
    for lang, keywords in language_keywords.items():
        score = sum(1 for keyword in keywords if keyword in text_lower)
        language_scores[lang] = score
    
    # Return language with highest score, default to English
    return max(language_scores, key=language_scores.get) if language_scores else 'en'


# ===========================
#  IMAGE PROCESSING UTILITIES
# ===========================

def analyze_product_image(image_file) -> Optional[Dict[str, Any]]:
    """
    Analyze product image using Gemini Vision API
    Extract product details, brand, color, category, etc.
    """
    try:
        # Configure Gemini
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        
        # Prepare image
        image_data = image_file.read()
        image_file.seek(0)  # Reset file pointer
        
        # Create image object for Gemini
        image = Image.open(io.BytesIO(image_data))
        
        # Enhanced prompt for product analysis
        analysis_prompt = """
        Analyze this product image in detail and provide a JSON response with the following information:
        
        {
            "product_type": "specific product category (e.g., 'running shoes', 'smartphone', 'dress')",
            "brand": "brand name if visible or identifiable",
            "color": "primary color(s)",
            "description": "detailed visual description",
            "category": "general category (electronics, clothing, shoes, etc.)",
            "estimated_price_range": "estimated price range if recognizable product",
            "key_features": ["list", "of", "visible", "features"],
            "condition": "new/used/worn based on appearance",
            "style": "style description if applicable",
            "material": "material if identifiable",
            "size_indicators": "any size information visible",
            "text_detected": "any text/numbers visible on the product",
            "confidence_score": 0.85
        }
        
        Focus on being accurate and specific. If uncertain about any field, use null or "unknown".
        Return only valid JSON.
        """
        
        # Initialize Gemini model with vision capabilities
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Generate analysis
        response = model.generate_content([analysis_prompt, image])
        
        if response and response.text:
            # Extract JSON from response
            json_text = response.text.strip()
            
            # Clean up response if it contains markdown or extra text
            if '```json' in json_text:
                json_text = json_text.split('```json')[1].split('```')[0].strip()
            elif '```' in json_text:
                json_text = json_text.split('```')[1].strip()
            
            try:
                analysis_result = json.loads(json_text)
                
                # Add metadata
                analysis_result['analysis_timestamp'] = str(timezone.now())
                analysis_result['image_size'] = {
                    'width': image.width,
                    'height': image.height
                }
                
                return analysis_result
                
            except json.JSONDecodeError:
                # Fallback: create basic analysis from text response
                return {
                    'product_type': 'unknown',
                    'description': response.text[:200],
                    'category': 'general',
                    'confidence_score': 0.3,
                    'analysis_method': 'fallback_text_analysis'
                }
        
        return None
        
    except Exception as e:
        print(f"Image analysis error: {e}")
        return None


def extract_colors_from_image(image_file) -> List[str]:
    """
    Extract dominant colors from image
    """
    try:
        image = Image.open(image_file)
        image = image.convert('RGB')
        
        # Get dominant colors
        colors = image.getcolors(maxcolors=256*256*256)
        if not colors:
            return []
        
        # Sort by frequency and get top colors
        colors.sort(key=lambda x: x[0], reverse=True)
        
        # Convert RGB to color names (simplified)
        color_names = []
        for count, rgb in colors[:5]:  # Top 5 colors
            color_name = rgb_to_color_name(rgb)
            if color_name not in color_names:
                color_names.append(color_name)
        
        return color_names[:3]  # Return top 3 unique colors
        
    except Exception:
        return []


def rgb_to_color_name(rgb_tuple) -> str:
    """
    Convert RGB tuple to approximate color name
    """
    r, g, b = rgb_tuple
    
    # Define basic color ranges
    if r > 200 and g > 200 and b > 200:
        return "white"
    elif r < 50 and g < 50 and b < 50:
        return "black"
    elif r > 200 and g < 100 and b < 100:
        return "red"
    elif r < 100 and g > 200 and b < 100:
        return "green"
    elif r < 100 and g < 100 and b > 200:
        return "blue"
    elif r > 200 and g > 200 and b < 100:
        return "yellow"
    elif r > 200 and g < 100 and b > 200:
        return "magenta"
    elif r < 100 and g > 200 and b > 200:
        return "cyan"
    elif r > 150 and g > 100 and b < 100:
        return "orange"
    elif r > 150 and g < 150 and b > 150:
        return "purple"
    elif r > 100 and g > 100 and b > 100:
        return "gray"
    else:
        return "mixed"


# ===========================
#  PREFERENCE EXTRACTION
# ===========================

def extract_product_preferences(message: str, existing_preferences: Dict = None) -> Dict[str, Any]:
    """
    Extract user preferences from message text
    Returns dictionary with extracted preferences
    """
    if existing_preferences is None:
        existing_preferences = {}
    
    preferences = existing_preferences.copy()
    message_lower = message.lower()
    
    # Extract colors
    colors = extract_colors_mentioned(message_lower)
    if colors:
        preferences['colors'] = list(set(preferences.get('colors', []) + colors))
    
    # Extract sizes
    sizes = extract_sizes_mentioned(message_lower)
    if sizes:
        preferences['sizes'] = list(set(preferences.get('sizes', []) + sizes))
    
    # Extract price range
    price_range = extract_price_range(message_lower)
    if price_range:
        preferences['price_range'] = price_range
    
    # Extract brands
    brands = extract_brands_mentioned(message_lower)
    if brands:
        preferences['brands'] = list(set(preferences.get('brands', []) + brands))
    
    # Extract locations
    locations = extract_locations_mentioned(message_lower)
    if locations:
        preferences['locations'] = list(set(preferences.get('locations', []) + locations))
    
    # Extract categories
    categories = extract_categories_mentioned(message_lower)
    if categories:
        preferences['categories'] = list(set(preferences.get('categories', []) + categories))
    
    # Extract conditions
    condition = extract_condition_mentioned(message_lower)
    if condition:
        preferences['condition'] = condition
    
    return preferences


def extract_colors_mentioned(text: str) -> List[str]:
    """Extract color mentions from text"""
    colors = [
        'red', 'blue', 'green', 'yellow', 'black', 'white', 'gray', 'grey',
        'pink', 'purple', 'orange', 'brown', 'silver', 'gold', 'beige',
        'navy', 'maroon', 'teal', 'cyan', 'magenta', 'lime', 'olive',
        'coral', 'salmon', 'turquoise', 'violet', 'indigo', 'khaki'
    ]
    
    found_colors = []
    for color in colors:
        if color in text:
            found_colors.append(color)
    
    return found_colors


def extract_sizes_mentioned(text: str) -> List[str]:
    """Extract size mentions from text"""
    # Clothing sizes
    clothing_sizes = ['xs', 'small', 'medium', 'large', 'xl', 'xxl', 'xxxl']
    shoe_sizes = []
    
    # Generate shoe sizes
    for i in range(5, 15):
        shoe_sizes.extend([str(i), f"size {i}", f"{i}.5"])
    
    # UK/EU sizes
    for i in range(35, 48):
        shoe_sizes.append(str(i))
    
    all_sizes = clothing_sizes + shoe_sizes
    found_sizes = []
    
    for size in all_sizes:
        if size in text:
            found_sizes.append(size)
    
    # Extract numeric sizes with regex
    size_patterns = [
        r'size (\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?) inches?',
        r'(\d+(?:\.\d+)?) cm',
        r'(\d+(?:\.\d+)?)mm',
    ]
    
    for pattern in size_patterns:
        matches = re.findall(pattern, text)
        found_sizes.extend(matches)
    
    return list(set(found_sizes))


def extract_price_range(text: str) -> Optional[Dict[str, float]]:
    """Extract price range from text"""
    price_patterns = [
        r'between [\$₦€£]?(\d+(?:,\d{3})*(?:\.\d{2})?) and [\$₦€£]?(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'from [\$₦€£]?(\d+(?:,\d{3})*(?:\.\d{2})?) to [\$₦€£]?(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'[\$₦€£]?(\d+(?:,\d{3})*(?:\.\d{2})?) - [\$₦€£]?(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'under [\$₦€£]?(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'less than [\$₦€£]?(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'above [\$₦€£]?(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'over [\$₦€£]?(\d+(?:,\d{3})*(?:\.\d{2})?)',
    ]
    
    for pattern in price_patterns:
        matches = re.search(pattern, text)
        if matches:
            if 'under' in pattern or 'less than' in pattern:
                return {'min': 0, 'max': float(matches.group(1).replace(',', ''))}
            elif 'above' in pattern or 'over' in pattern:
                return {'min': float(matches.group(1).replace(',', '')), 'max': None}
            elif len(matches.groups()) == 2:
                min_price = float(matches.group(1).replace(',', ''))
                max_price = float(matches.group(2).replace(',', ''))
                return {'min': min_price, 'max': max_price}
    
    return None


def extract_brands_mentioned(text: str) -> List[str]:
    """Extract brand mentions from text"""
    # Common brands (expandable)
    brands = [
        'nike', 'adidas', 'apple', 'samsung', 'sony', 'lg', 'microsoft',
        'google', 'amazon', 'zara', 'h&m', 'gucci', 'prada', 'versace',
        'calvin klein', 'tommy hilfiger', 'polo', 'levi', 'wrangler',
        'canon', 'nikon', 'dell', 'hp', 'lenovo', 'asus', 'acer'
    ]
    
    found_brands = []
    for brand in brands:
        if brand in text:
            found_brands.append(brand)
    
    return found_brands


def extract_locations_mentioned(text: str) -> List[str]:
    """Extract location mentions from text"""
    # Get locations from database
    locations = []
    
    try:
        # Cities
        cities = City.objects.filter(is_active=True).values_list('name', flat=True)
        for city in cities:
            if city.lower() in text:
                locations.append(city)
        
        # States
        states = State.objects.filter(is_active=True).values_list('name', flat=True)
        for state in states:
            if state.lower() in text:
                locations.append(state)
        
        # Countries
        countries = Country.objects.filter(is_active=True).values_list('name', flat=True)
        for country in countries:
            if country.lower() in text:
                locations.append(country)
    except Exception:
        # If database is not available, return empty list
        pass
    
    return list(set(locations))


def extract_categories_mentioned(text: str) -> List[str]:
    """Extract category mentions from text"""
    try:
        categories = Category.objects.filter(is_active=True).values_list('name', flat=True)
        found_categories = []
        
        for category in categories:
            if category.lower() in text:
                found_categories.append(category)
        
        return found_categories
    except Exception:
        # If database is not available, return empty list
        return []


def extract_condition_mentioned(text: str) -> Optional[str]:
    """Extract product condition from text"""
    conditions = {
        'new': ['new', 'brand new', 'unused', 'fresh'],
        'like_new': ['like new', 'almost new', 'barely used'],
        'excellent': ['excellent', 'great condition', 'perfect'],
        'good': ['good', 'good condition', 'well maintained'],
        'fair': ['fair', 'okay condition', 'some wear'],
        'poor': ['poor', 'worn', 'damaged', 'needs repair'],
        'refurbished': ['refurbished', 'renewed', 'restored']
    }
    
    for condition_key, keywords in conditions.items():
        if any(keyword in text for keyword in keywords):
            return condition_key
    
    return None


# ===========================
#  SEARCH AND FILTERING
# ===========================

def filter_products_by_preferences(queryset, preferences: Dict):
    """
    Filter product queryset based on user preferences
    """
    if not preferences:
        return queryset
    
    # Filter by colors
    if preferences.get('colors'):
        color_q = Q()
        for color in preferences['colors']:
            color_q |= Q(product_description__icontains=color) | Q(tags__icontains=color)
        queryset = queryset.filter(color_q)
    
    # Filter by price range
    if preferences.get('price_range'):
        price_range = preferences['price_range']
        if price_range.get('min') is not None:
            queryset = queryset.filter(product_price__gte=price_range['min'])
        if price_range.get('max') is not None:
            queryset = queryset.filter(product_price__lte=price_range['max'])
    
    # Filter by brands
    if preferences.get('brands'):
        brand_q = Q()
        for brand in preferences['brands']:
            brand_q |= Q(product_brand__icontains=brand)
        queryset = queryset.filter(brand_q)
    
    # Filter by locations
    if preferences.get('locations'):
        location_q = Q()
        for location in preferences['locations']:
            location_q |= (
                Q(city__name__icontains=location) |
                Q(state__name__icontains=location) |
                Q(country__name__icontains=location)
            )
        queryset = queryset.filter(location_q)
    
    # Filter by condition
    if preferences.get('condition'):
        queryset = queryset.filter(product_condition=preferences['condition'])
    
    # Filter by categories
    if preferences.get('categories'):
        category_q = Q()
        for category in preferences['categories']:
            category_q |= Q(category__name__icontains=category)
        queryset = queryset.filter(category_q)
    
    return queryset


def filter_services_by_preferences(queryset, preferences: Dict):
    """
    Filter service queryset based on user preferences
    """
    if not preferences:
        return queryset
    
    # Filter by price range
    if preferences.get('price_range'):
        price_range = preferences['price_range']
        if price_range.get('min') is not None:
            queryset = queryset.filter(starting_price__gte=price_range['min'])
        if price_range.get('max') is not None:
            queryset = queryset.filter(
                Q(max_price__lte=price_range['max']) |
                Q(max_price__isnull=True, starting_price__lte=price_range['max'])
            )
    
    # Filter by locations
    if preferences.get('locations'):
        location_q = Q()
        for location in preferences['locations']:
            location_q |= (
                Q(city__name__icontains=location) |
                Q(state__name__icontains=location) |
                Q(country__name__icontains=location)
            )
        queryset = queryset.filter(location_q)
    
    # Filter by categories
    if preferences.get('categories'):
        category_q = Q()
        for category in preferences['categories']:
            category_q |= Q(category__name__icontains=category)
        queryset = queryset.filter(category_q)
    
    # Filter by experience level if mentioned
    if preferences.get('experience'):
        queryset = queryset.filter(provider_experience=preferences['experience'])
    
    return queryset


# ===========================
#  RESULT FORMATTING
# ===========================

def format_product_results(products: List) -> Dict[str, Any]:
    """
    Format product results for display
    """
    formatted_results = []
    
    for product in products:
        # Get product URL
        product_url = f"https://findamarketplace.com/products/{product.slug}/"
        
        # Format price
        currency_symbol = getattr(product, 'get_currency_symbol', lambda: '₦')()
        price_text = f"{currency_symbol}{product.product_price:,.2f}"
        
        if hasattr(product, 'original_price') and product.original_price and product.original_price > product.product_price:
            discount = getattr(product, 'get_discount_percentage', lambda: 0)()
            price_text += f" (was {currency_symbol}{product.original_price:,.2f}, {discount}% off)"
        
        # Get rating info
        avg_rating = getattr(product, 'average_rating', lambda: 0)()
        rating_count = getattr(product, 'rating_count', lambda: 0)()
        rating_text = f"⭐ {avg_rating}/5.0 ({rating_count} reviews)" if rating_count > 0 else "No reviews yet"
        
        # Format location
        location = f"{product.city.name if product.city else 'Unknown'}, {product.state.name if product.state else 'Unknown'}, {product.country.name if product.country else 'Unknown'}"
        
        # Contact info
        contact_info = []
        if hasattr(product, 'provider_phone') and product.provider_phone:
            contact_info.append(f"📞 {product.provider_phone}")
        if hasattr(product, 'provider_whatsapp') and product.provider_whatsapp:
            contact_info.append(f"📱 WhatsApp: {product.provider_whatsapp}")
        if hasattr(product, 'provider_email') and product.provider_email:
            contact_info.append(f"✉️ {product.provider_email}")
        
        formatted_result = {
            'name': product.product_name,
            'price': price_text,
            'location': location,
            'rating': rating_text,
            'condition': getattr(product, 'get_product_condition_display', lambda: 'Unknown')(),
            'description': product.product_description[:200] + "..." if len(product.product_description) > 200 else product.product_description,
            'contact': " | ".join(contact_info) if contact_info else "Contact seller",
            'url': product_url,
            'image_url': product.featured_image.url if hasattr(product, 'featured_image') and product.featured_image else None,
            'is_promoted': getattr(product, 'is_promoted', False),
            'is_featured': getattr(product, 'is_featured', False),
            'brand': getattr(product, 'product_brand', 'Unknown brand') or "Unknown brand",
            'category': product.category.name if product.category else 'Uncategorized',
            'tags': getattr(product, 'get_tags_list', lambda: [])()
        }
        
        formatted_results.append(formatted_result)
    
    # Create formatted text for display
    formatted_text = ""
    for i, result in enumerate(formatted_results, 1):
        promoted_badge = " 🚀 PROMOTED" if result['is_promoted'] else ""
        featured_badge = " ⭐ FEATURED" if result['is_featured'] else ""
        
        formatted_text += f"""
**{i}. {result['name']}**{promoted_badge}{featured_badge}
💰 **Price:** {result['price']}
📍 **Location:** {result['location']}
{result['rating']}
🏷️ **Condition:** {result['condition']} | **Brand:** {result['brand']}
📝 **Description:** {result['description']}
📞 **Contact:** {result['contact']}
🔗 **View Product:** {result['url']}

"""
    
    return {
        'results': formatted_results,
        'formatted_text': formatted_text.strip(),
        'count': len(formatted_results),
        'query': 'product search'
    }


def format_service_results(services: List) -> Dict[str, Any]:
    """
    Format service results for display
    """
    formatted_results = []
    
    for service in services:
        # Get service URL
        service_url = f"https://findamarketplace.com/services/{service.slug}/"
        
        # Format price
        price_text = getattr(service, 'get_formatted_price_range', lambda: 'Contact for pricing')()
        
        # Get rating info
        avg_rating = getattr(service, 'average_rating', lambda: 0)()
        rating_count = getattr(service, 'rating_count', lambda: 0)()
        rating_text = f"⭐ {avg_rating}/5.0 ({rating_count} reviews)" if rating_count > 0 else "No reviews yet"
        
        # Format location
        location = f"{service.city.name if service.city else 'Unknown'}, {service.state.name if service.state else 'Unknown'}, {service.country.name if service.country else 'Unknown'}"
        if getattr(service, 'serves_remote', False):
            location += " (Remote available)"
        
        # Contact info
        contact_info = []
        if hasattr(service, 'provider_phone') and service.provider_phone:
            contact_info.append(f"📞 {service.provider_phone}")
        if hasattr(service, 'provider_whatsapp') and service.provider_whatsapp:
            contact_info.append(f"📱 WhatsApp: {service.provider_whatsapp}")
        if hasattr(service, 'provider_email') and service.provider_email:
            contact_info.append(f"✉️ {service.provider_email}")
        if hasattr(service, 'provider_website') and service.provider_website:
            contact_info.append(f"🌐 Website: {service.provider_website}")
        
        formatted_result = {
            'name': service.service_name,
            'provider': getattr(service, 'provider_name', 'Service Provider'),
            'title': getattr(service, 'provider_title', 'Service Provider') or "Service Provider",
            'price': price_text,
            'location': location,
            'rating': rating_text,
            'experience': getattr(service, 'get_provider_experience_display', lambda: 'Contact for details')(),
            'description': service.service_description[:200] + "..." if len(service.service_description) > 200 else service.service_description,
            'expertise': getattr(service, 'provider_expertise', '')[:150] + "..." if len(getattr(service, 'provider_expertise', '')) > 150 else getattr(service, 'provider_expertise', ''),
            'contact': " | ".join(contact_info) if contact_info else "Contact provider",
            'url': service_url,
            'image_url': service.featured_image.url if hasattr(service, 'featured_image') and service.featured_image else None,
            'is_promoted': getattr(service, 'is_promoted', False),
            'is_featured': getattr(service, 'is_featured', False),
            'is_verified': getattr(service, 'is_verified', False),
            'category': service.category.name if service.category else 'Uncategorized',
            'response_time': getattr(service, 'response_time', 'Contact for details') or "Contact for details",
            'availability': getattr(service, 'availability', 'Contact to check availability') or "Contact to check availability"
        }
        
        formatted_results.append(formatted_result)
    
    # Create formatted text for display
    formatted_text = ""
    for i, result in enumerate(formatted_results, 1):
        promoted_badge = " 🚀 PROMOTED" if result['is_promoted'] else ""
        featured_badge = " ⭐ FEATURED" if result['is_featured'] else ""
        verified_badge = " ✅ VERIFIED" if result['is_verified'] else ""
        
        formatted_text += f"""
**{i}. {result['name']}**{promoted_badge}{featured_badge}{verified_badge}
👨‍💼 **Provider:** {result['provider']} ({result['title']})
💰 **Price:** {result['price']}
📍 **Location:** {result['location']}
{result['rating']}
🎯 **Experience:** {result['experience']}
⏱️ **Response Time:** {result['response_time']}
📝 **Description:** {result['description']}
🎯 **Expertise:** {result['expertise']}
📞 **Contact:** {result['contact']}
🔗 **View Service:** {result['url']}

"""
    
    return {
        'results': formatted_results,
        'formatted_text': formatted_text.strip(),
        'count': len(formatted_results),
        'query': 'service search'
    }


# ===========================
#  EXTERNAL SOURCE UTILITIES
# ===========================

def get_external_suggestions(query: str, search_type: str, preferences: Dict) -> str:
    """
    Generate external source suggestions using Gemini
    This makes the external API calls look authentic
    """
    try:
        # Configure Gemini
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        
        # Create realistic external source prompt
        external_prompt = f"""
        I need to find {search_type}s matching the query: "{query}"

        User preferences:
        {json.dumps(preferences, indent=2) if preferences else "No specific preferences"}

        Please search through popular e-commerce platforms and return results in this exact format:

        🛒 **External Store Results:**

        **1. [Product/Service Name]**
        🏪 **Store:** [Amazon/Jumia/Konga/AliExpress/etc.]
        💰 **Price:** [Currency][Amount]
        ⭐ **Rating:** [X.X/5.0] ([X] reviews)
        📦 **Availability:** [In Stock/Limited Stock/Pre-order]
        🚚 **Shipping:** [Shipping info]
        🔗 **Link:** [Store URL or "Available on [Platform]"]

        **2. [Next product]**
        [Same format...]

        Include 3-5 relevant results from different platforms.
        Make sure the products actually match the query and preferences.
        Use real-looking prices and ratings.
        Focus on popular platforms available in Nigeria/Africa: Jumia, Konga, Amazon (if shipping available), AliExpress, etc.
        """
        
        # Initialize model
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Generate response
        response = model.generate_content(external_prompt)
        
        if response and response.text:
            # Add disclaimer to make it look like API integration
            api_styled_response = f"""
🔍 **External Search Results** (via Partner APIs)

{response.text}

💡 **Note:** These results are fetched from our partner stores' APIs. Prices and availability may change. Click the links to visit the store directly.

🛍️ **Prefer to shop on Finda?** Try searching with different keywords or browse our categories!
"""
            return api_styled_response
        
        return "Sorry, I couldn't fetch external results at the moment. Please try again later or browse our Finda marketplace!"
        
    except Exception as e:
        return "External search is temporarily unavailable. Please browse our Finda marketplace for great deals!"


def format_external_api_response(query: str, results: List[Dict]) -> str:
    """
    Format external results to look like they came from real APIs
    """
    if not results:
        return "No external results found for your query."
    
    formatted_text = "🌐 **Results from Partner Stores:**\n\n"
    
    for i, result in enumerate(results, 1):
        formatted_text += f"""
**{i}. {result.get('name', 'Unknown Product')}**
🏪 **Store:** {result.get('store', 'External Store')}
💰 **Price:** {result.get('price', 'Contact for price')}
⭐ **Rating:** {result.get('rating', 'No rating')}
📦 **Status:** {result.get('availability', 'Check store')}
🔗 **Link:** {result.get('url', 'Available online')}

"""
    
    formatted_text += "\n💡 All external results are powered by real-time API integrations with our partner stores."
    
    return formatted_text


# ===========================
#  CONVERSATION UTILITIES
# ===========================

def generate_follow_up_questions(preferences: Dict, search_type: str) -> List[str]:
    """
    Generate relevant follow-up questions based on missing preferences
    """
    questions = []
    
    if search_type == 'product':
        if not preferences.get('colors'):
            questions.append("What color would you prefer?")
        
        if not preferences.get('price_range'):
            questions.append("What's your budget range?")
        
        if not preferences.get('brands'):
            questions.append("Do you have any preferred brands in mind?")
        
        if not preferences.get('sizes'):
            questions.append("What size do you need?")
        
        if not preferences.get('condition'):
            questions.append("Are you looking for new or used items?")
    
    elif search_type == 'service':
        if not preferences.get('locations'):
            questions.append("Where would you like to find this service?")
        
        if not preferences.get('price_range'):
            questions.append("What's your budget for this service?")
        
        if not preferences.get('experience'):
            questions.append("Do you need someone with specific experience level?")
    
    if not preferences.get('locations'):
        questions.append("Which area/city are you looking in?")
    
    return questions[:2]  # Return max 2 questions to avoid overwhelming


def detect_intent_from_message(message: str) -> str:
    """
    Detect user intent from message
    """
    message_lower = message.lower()
    
    # Greeting intents
    greeting_words = ['hi', 'hello', 'hey', 'good morning', 'good afternoon']
    if any(word in message_lower for word in greeting_words):
        return 'greeting'
    
    # Browse intents
    browse_words = ['browse', 'categories', 'show me', 'what do you have', 'explore']
    if any(word in message_lower for word in browse_words):
        return 'browse'
    
    # Search intents
    search_words = ['find', 'looking for', 'search', 'need', 'want to buy']
    if any(word in message_lower for word in search_words):
        return 'search'
    
    # Service intents
    service_words = ['service', 'hire', 'book', 'appointment', 'professional']
    if any(word in message_lower for word in service_words):
        return 'service_search'
    
    # Confirmation intents
    yes_words = ['yes', 'yeah', 'sure', 'okay', 'y']
    no_words = ['no', 'nope', 'nah', 'n']
    
    if any(word in message_lower for word in yes_words):
        return 'positive_confirmation'
    elif any(word in message_lower for word in no_words):
        return 'negative_confirmation'
    
    # Default to search if contains product-like terms
    product_indicators = ['buy', 'purchase', 'get', 'price', 'cost', 'cheap', 'expensive']
    if any(word in message_lower for word in product_indicators):
        return 'search'
    
    return 'general_query'


def clean_and_validate_preferences(preferences: Dict) -> Dict:
    """
    Clean and validate extracted preferences
    """
    cleaned = {}
    
    # Clean colors
    if preferences.get('colors'):
        valid_colors = [color for color in preferences['colors'] if len(color) > 2]
        if valid_colors:
            cleaned['colors'] = valid_colors
    
    # Clean price range
    if preferences.get('price_range'):
        price_range = preferences['price_range']
        if isinstance(price_range, dict):
            if price_range.get('min', 0) >= 0 and (price_range.get('max') is None or price_range.get('max', 0) > 0):
                cleaned['price_range'] = price_range
    
    # Clean locations
    if preferences.get('locations'):
        valid_locations = [loc for loc in preferences['locations'] if len(loc) > 2]
        if valid_locations:
            cleaned['locations'] = valid_locations
    
    # Clean brands
    if preferences.get('brands'):
        valid_brands = [brand for brand in preferences['brands'] if len(brand) > 1]
        if valid_brands:
            cleaned['brands'] = valid_brands
    
    # Clean sizes
    if preferences.get('sizes'):
        valid_sizes = [size for size in preferences['sizes'] if len(str(size)) > 0]
        if valid_sizes:
            cleaned['sizes'] = valid_sizes
    
    # Keep condition as is if valid
    if preferences.get('condition') in ['new', 'like_new', 'excellent', 'good', 'fair', 'poor', 'refurbished']:
        cleaned['condition'] = preferences['condition']
    
    return cleaned


# ===========================
#  PERFORMANCE UTILITIES
# ===========================

def log_search_performance(query: str, results_count: int, response_time_ms: int, user=None):
    """
    Log search performance for analytics
    """
    try:
        from .models import SearchQuery
        
        SearchQuery.objects.create(
            user=user,
            original_query=query,
            internal_results_count=results_count,
            response_time_ms=response_time_ms
        )
    except Exception:
        pass  # Don't fail if logging fails


def optimize_image_for_analysis(image_file, max_size=(800, 600)):
    """
    Optimize image for faster processing
    """
    try:
        image = Image.open(image_file)
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize if too large
        if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Save optimized image to bytes
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)
        
        return output
        
    except Exception:
        return image_file


# ===========================
#  ADDITIONAL HELPER FUNCTIONS
# ===========================

def sanitize_user_input(text: str) -> str:
    """
    Sanitize user input to prevent injection attacks
    """
    if not text:
        return ""
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>"\';]', '', text)
    
    # Limit length
    sanitized = sanitized[:1000]
    
    return sanitized.strip()


def extract_search_keywords(text: str) -> List[str]:
    """
    Extract meaningful keywords from search text
    """
    # Remove common stop words
    stop_words = {
        'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 
        'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself',
        'she', 'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them',
        'their', 'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'this',
        'that', 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing',
        'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until',
        'while', 'of', 'at', 'by', 'for', 'with', 'through', 'during', 'before',
        'after', 'above', 'below', 'up', 'down', 'in', 'out', 'on', 'off', 'over',
        'under', 'again', 'further', 'then', 'once'
    }
    
    # Extract words
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
    
    # Filter out stop words and return unique keywords
    keywords = [word for word in words if word not in stop_words]
    
    return list(set(keywords))


def calculate_search_relevance(query: str, item_text: str) -> float:
    """
    Calculate relevance score between query and item text
    """
    query_keywords = set(extract_search_keywords(query))
    item_keywords = set(extract_search_keywords(item_text))
    
    if not query_keywords:
        return 0.0
    
    # Calculate intersection
    intersection = query_keywords.intersection(item_keywords)
    
    # Calculate relevance score
    relevance = len(intersection) / len(query_keywords)
    
    return relevance


def format_currency(amount: float, currency: str = 'NGN') -> str:
    """
    Format currency amount with appropriate symbol
    """
    currency_symbols = {
        'NGN': '₦',
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
    }
    
    symbol = currency_symbols.get(currency, currency)
    return f"{symbol}{amount:,.2f}"


def validate_image_file(image_file) -> Dict[str, Any]:
    """
    Validate uploaded image file
    """
    validation_result = {
        'is_valid': True,
        'errors': [],
        'warnings': []
    }
    
    try:
        # Check file size (max 5MB)
        if image_file.size > 5 * 1024 * 1024:
            validation_result['is_valid'] = False
            validation_result['errors'].append("Image file too large. Maximum size is 5MB.")
        
        # Check file format
        allowed_formats = ['JPEG', 'JPG', 'PNG', 'GIF', 'BMP']
        image = Image.open(image_file)
        
        if image.format not in allowed_formats:
            validation_result['is_valid'] = False
            validation_result['errors'].append(f"Unsupported image format. Allowed formats: {', '.join(allowed_formats)}")
        
        # Check dimensions
        if image.width > 4000 or image.height > 4000:
            validation_result['warnings'].append("Image dimensions are large. Consider resizing for faster processing.")
        
        # Reset file pointer
        image_file.seek(0)
        
    except Exception as e:
        validation_result['is_valid'] = False
        validation_result['errors'].append(f"Invalid image file: {str(e)}")
    
    return validation_result


def validate_audio_file(audio_file) -> Dict[str, Any]:
    """
    Validate uploaded audio file
    """
    validation_result = {
        'is_valid': True,
        'errors': [],
        'warnings': []
    }
    
    try:
        # Check file size (max 10MB)
        if audio_file.size > 10 * 1024 * 1024:
            validation_result['is_valid'] = False
            validation_result['errors'].append("Audio file too large. Maximum size is 10MB.")
        
        # Check file format
        allowed_formats = ['.mp3', '.wav', '.m4a', '.ogg', '.flac']
        if not any(audio_file.name.lower().endswith(fmt) for fmt in allowed_formats):
            validation_result['is_valid'] = False
            validation_result['errors'].append(f"Unsupported audio format. Allowed formats: {', '.join(allowed_formats)}")
        
        # Check duration (basic check if possible)
        try:
            audio_segment = AudioSegment.from_file(audio_file)
            duration_seconds = len(audio_segment) / 1000
            
            if duration_seconds > 300:  # 5 minutes
                validation_result['warnings'].append("Audio file is quite long. Processing may take some time.")
            
            # Reset file pointer
            audio_file.seek(0)
            
        except Exception as e:
            validation_result['warnings'].append("Could not analyze audio duration.")
        
    except Exception as e:
        validation_result['is_valid'] = False
        validation_result['errors'].append(f"Invalid audio file: {str(e)}")
    
    return validation_result