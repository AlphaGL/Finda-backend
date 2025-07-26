# views.py - Enhanced with image and voice endpoints
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage

from .gemini_client import (
    send_to_gemini, analyze_image_with_gemini, 
    transcribe_audio, generate_voice_response
)
from .models import ChatMessage, UserVoiceSettings
from .serializers import ChatMessageSerializer, VoiceSettingsSerializer
from .utils import find_exact_matches, search_products_by_analysis
from main.models import Products, Services, Category

User = get_user_model()

# — SYSTEM PROMPT (used on first message only) —
SYSTEM_PROMPT = (
    "You are the Finda shopping assistant. "
    "Greet the user: 'Hello, welcome to Finda! What can we help you find today?' "
    "When the user asks for a product or service, first search Finda's database. "
    "If matches exist, list the top 3 by rating and then ask: "
    "'Would you also like suggestions from external stores (Amazon, Jumia, etc.)?' "
    "If no matches, intelligently suggest alternatives using external sources. "
    "You can also help with voice messages and image searches to find products."
)

# Intent dictionaries (keeping your existing ones)
GREETINGS = {
    "hi", "hello", "hey", "hiya", "yo", "howdy", "sup", "what's up", "hey there", "g'day", "how's it going",
    "good morning", "good afternoon", "good evening", "evening", "morning", "good day",
    "bonjour", "salut", "bonsoir", "hola", "buenos días", "buenas tardes", "buenas noches",
    "guten tag", "guten morgen", "guten abend", "ciao", "buongiorno", "buonasera",
    "olá", "bom dia", "boa tarde", "boa noite", "hallo", "goede dag", "goedemorgen",
    "goedenavond", "привет", "здравствуйте", "доброе утро", "добрый день", "добрый вечер",
    "مرحبا", "اهلا", "السلام عليكم", "صباح الخير", "مساء الخير",
    "你好", "您好", "早上好", "下午好", "晚上好", "こんにちは", "おはよう", "おはようございます", "こんばんは",
    "안녕하세요", "안녕", "좋은 아침", "좋은 저녁", "नमस्ते", "नमस्कार", "सुप्रभात", "शुभ संध्या",
    "ẹ n lẹ", "bawo ni", "kaaro", "kaasan", "kaale", "ndewo", "ututu oma", "ehihie oma", "mgbede oma",
    "sannu", "ina kwana", "ina wuni", "barka da safiya", "barka da rana", "barka da yamma",
    "habari", "hujambo", "salama", "shikamoo", "asubuhi njema", "jioni njema"
}

THANKS = {
    "thanks", "thank you", "thanks a lot", "thank you so much", "thanks so much",
    "many thanks", "much appreciated", "cheers", "thanks a ton", "thank you kindly",
    "thx", "ty", "tysm", "tnx", "tq", "appreciate it", "thank u", "big thanks", "thanx", "tanks",
    "merci", "merci beaucoup", "grand merci", "gracias", "muchas gracias", "mil gracias",
    "danke", "vielen dank", "danke schön", "tausend dank", "grazie", "mille grazie", "grazie mille",
    "obrigado", "obrigada", "muito obrigado", "muito obrigada", "dank je", "dank je wel", "bedankt",
    "hartelijk dank", "спасибо", "большое спасибо", "спасибки", "شكرا", "شكراً جزيلاً", "ألف شكر",
    "谢谢", "谢谢你", "多谢", "非常感谢", "ありがとう", "ありがとうございます", "どうもありがとう",
    "감사합니다", "고맙습니다", "고마워", "감사해요", "धन्यवाद", "शुक्रिया", "बहुत धन्यवाद",
    "ẹ se", "ẹ ṣé púpọ̀", "o se", "o seun", "daalụ", "imeela", "ekele diri gị",
    "na gode", "nagode sosai", "asante", "asante sana", "nashukuru", "ahsante"
}

POSITIVE_CONFIRMATIONS = {
    "yes", "yeah", "yep", "yup", "yah", "ya", "sure", "sure thing", "absolutely", "definitely",
    "for sure", "of course", "okay", "ok", "okey", "okey dokey", "alright", "roger that",
    "affirmative", "you got it", "sounds good", "why not", "go ahead", "let's do it",
    "let's go", "please do", "yess", "yesss", "yea", "yuh", "bet", "ight", "100%", "on god",
    "aye", "hell yes", "hell yeah", "fo sho", "for real", "no doubt", "yup please",
    "yes please", "that would be great", "yes do", "yes sure", "yes it is", "yes i do",
    "do it", "do that", "go on", "i want that", "yes go ahead", "yes why not",
    "y", "yaas", "yaaas", "yaaaas", "yaa", "u bet", "u got it", "okie", "okies", "okok",
    "oui", "bien sûr", "absolument", "d'accord", "ouais", "c'est bon", "okey",
    "sí", "claro", "por supuesto", "vale", "cierto", "desde luego",
    "ja", "natürlich", "klar", "sicher", "auf jeden fall", "sì", "certamente", "ovviamente",
    "va bene", "d'accordo", "sim", "claro", "com certeza", "pois não", "certo",
    "ja", "zeker", "natuurlijk", "oké", "tuurlijk", "да", "конечно", "безусловно", "ага",
    "نعم", "أكيد", "طبعا", "تمام", "أجل", "ايوا", "是", "对", "好的", "没问题", "行", "当然",
    "はい", "ええ", "そうです", "もちろん", "了解です", "네", "예", "그럼요", "물론이죠", "좋아요",
    "हाँ", "जी हाँ", "बिलकुल", "हां", "bẹẹni", "bẹ́ẹ̀ ni", "ó dáa", "ko si wahala",
    "ee", "eh", "ọ dị mma", "ọ dị", "n'ezie", "eh", "e", "tabbas", "toh", "eh na'am",
    "ndiyo", "bila shaka", "sawa", "ndio", "hakika"
}

NEGATIVE_CONFIRMATIONS = {
    "no", "nope", "nah", "na", "not really", "not now", "maybe later", "not interested",
    "no thanks", "no thank you", "i'm good", "i'll pass", "not today", "no need",
    "don't bother", "don't worry about it", "pass", "hard pass", "no way", "absolutely not",
    "not at all", "not anymore", "not now thanks", "please no", "not for now",
    "nope not now", "never", "i'm fine", "i'm okay", "no i don't", "i don't want",
    "i don't need", "nah i'm good", "i'm okay thanks", "im good fam", "i'm good fr",
    "leave it", "forget it", "cancel", "i'm done", "that's all", "that's enough",
    "not necessary", "maybe next time", "n", "nuh uh", "no ty", "no tnx", "nope lol", "nah fam",
    "non", "pas maintenant", "non merci", "jamais", "aucune envie", "no", "nunca", "no gracias",
    "tal vez después", "ahora no", "nein", "nicht jetzt", "kein interesse", "ne danke",
    "auf keinen fall", "no", "non ora", "no grazie", "mai", "non adesso",
    "não", "não agora", "sem interesse", "não obrigado", "talvez depois",
    "nee", "niet nu", "nee dank je", "geen interesse", "нет", "не сейчас", "не надо",
    "никогда", "не хочу", "لا", "مش الآن", "مش مهتم", "لا شكراً", "لا أريد", "مش لازم",
    "不", "不是", "不用", "不要", "不可以", "不行", "没兴趣", "以后再说",
    "いいえ", "結構です", "いりません", "今はいい", "結構ですありがとう", "遠慮します",
    "아니요", "괜찮아요", "필요없어요", "지금은 아니에요", "사양할게요",
    "नहीं", "अभी नहीं", "धन्यवाद नहीं", "कोई ज़रूरत नहीं", "नहीं چाहیے",
    "rara", "rara o", "mi o fe", "ko ye mi", "ma fi sile", "ko to ye",
    "mba", "mba o", "a gaghi", "enweghị m mmasị", "hapụ ya", "i kwughị",
    "a'a", "ba yanzu ba", "bana so", "babu bukata", "a'a nagode",
    "hapana", "sio sasa", "sitaki", "hapana asante", "hapana shukrani"
}

BROWSE_PATTERNS = {
    "what do you have", "what you got", "what can i find", "show me what you have",
    "show me", "show products", "browse", "let me browse", "explore", "i want to explore",
    "browse your catalog", "see items", "see services", "see products", "what's available",
    "available items", "what are you offering", "check what you offer", "what are your offers",
    "open catalog", "list categories", "list services", "list products", "list items",
    "search all", "shop all", "shop now", "start shopping", "start browsing",
    "can i browse", "i want to see what's here", "display all", "view categories",
    "display your categories", "i want to check things out", "let me shop", "can i shop",
    "product categories", "services available", "explore items", "explore services",
    "let's explore", "let's shop", "i want to look around", "i want to window shop",
    "view catalog", "see your catalog", "check what you have", "go to marketplace"
}


class CustomAuthToken(APIView):
    permission_classes = [AllowAny]
    """
    POST /api-token-auth/
    Accepts email + password and returns token
    """
    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        password = request.data.get('password')

        if email is None or password is None:
            return Response({"error": "Email and password are required"}, status=400)

        user = authenticate(request, email=email, password=password)

        if not user:
            return Response({"error": "Invalid credentials"}, status=401)

        token, created = Token.objects.get_or_create(user=user)
        return Response({
            "token": token.key,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.get_full_name(),
            }
        })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_api(request):
    """Original chat API - keeping your exact logic"""
    user = request.user
    raw_message = request.data.get('message', '').strip()
    if not raw_message:
        return Response({"detail": "Please send a non-empty message."}, status=400)
    lower = raw_message.lower()

    # 1) Chat history - EXACT same logic
    recent = ChatMessage.objects.filter(user=user).order_by('-timestamp')[:10]
    history = []
    for msg in reversed(recent):
        history.append({'author': 'user', 'content': msg.user_input})
        history.append({'author': 'assistant', 'content': msg.bot_response})

    # 2) Add system prompt if new user - EXACT same logic
    if not recent.exists():
        history.insert(0, {'author': 'system', 'content': SYSTEM_PROMPT})

    try:
        # 3) Intent: Greeting - EXACT same logic
        if lower in GREETINGS:
            bot_text = "Hello, welcome to Finda! What can we help you find today?"

        # 4) Intent: Thank-you - EXACT same logic
        elif any(word in lower for word in THANKS):
            bot_text = "You're welcome! Let me know if you'd like to find anything else."

        # 5) Intent: Browse categories - EXACT same logic
        elif any(pat in lower for pat in BROWSE_PATTERNS):
            categories = [display for key, display in Category.CATEGORY_CHOICES if key != 'all']
            bot_text = (
                "Sure! Here are some categories you can explore:\n" +
                "\n".join(f"- {cat}" for cat in categories) +
                "\n\nOr just type in what you're looking for (e.g., 'Nike shoes', 'barber services').\n"
                "💡 Tip: You can also send me a photo of an item or record a voice message!"
            )

        else:
            # 6-11) All your existing logic remains exactly the same
            last_bot_msg = history[-1]['content'].lower() if history and history[-1]['author'] == 'assistant' else ""
            asked_external = "external stores" in last_bot_msg

            if asked_external and any(word in lower for word in POSITIVE_CONFIRMATIONS):
                bot_text = send_to_gemini(history, raw_message)

            elif asked_external and any(word in lower for word in NEGATIVE_CONFIRMATIONS):
                raise ValueError("Restarting DB search...")

            else:
                # Your exact database search logic
                prod_qs = Products.objects.filter(
                    Q(product_name__icontains=raw_message) |
                    Q(product_description__icontains=raw_message) |
                    Q(product_brand__icontains=raw_message),
                    product_status='published'
                )
                serv_qs = Services.objects.filter(
                    Q(service_name__icontains=raw_message) |
                    Q(service_description__icontains=raw_message),
                    service_status='published'
                )

                matches = list(prod_qs) + list(serv_qs)
                matches.sort(key=lambda obj: obj.average_rating(), reverse=True)

                if matches:
                    top3 = matches[:3]
                    response_lines = ["I found these on Finda:"]
                    for obj in top3:
                        url = getattr(obj, 'get_absolute_url', lambda: f'/products/{obj.pk}/')()
                        price = getattr(obj, 'product_price', getattr(obj, 'service_price', 'N/A'))
                        response_lines.append(f"- {obj} — ₦{price}\n  Link: https://yourdomain.com{url}")
                    response_lines.append(
                        "\nWould you also like suggestions from external stores (e.g., Amazon, Jumia)?"
                    )
                    bot_text = "\n".join(response_lines)
                else:
                    bot_text = send_to_gemini(history, raw_message)
    except Exception:
        bot_text = send_to_gemini(history, raw_message)
    
    # 12) Save conversation - EXACT same logic
    ChatMessage.objects.create(
        user=user,
        user_input=raw_message,
        bot_response=bot_text
    )
    return Response({"reply": bot_text})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def voice_chat_api(request):
    """NEW: Handle voice messages"""
    if 'audio' not in request.FILES:
        return Response({"error": "No audio file provided"}, status=400)
    
    audio_file = request.FILES['audio']
    user = request.user
    
    try:
        # Transcribe audio to text
        transcript = transcribe_audio(audio_file)
        
        if not transcript:
            return Response({
                "error": "Could not understand the audio. Please try speaking more clearly or use text instead."
            }, status=400)
        
        # Get user's voice settings
        voice_settings = getattr(user, 'voice_settings', None)
        voice_enabled = voice_settings.voice_enabled if voice_settings else True
        
        # Process the transcribed text using your existing chat logic
        # Create a mock request with the transcript
        chat_request_data = {'message': transcript}
        
        # Use your existing chat processing logic
        recent = ChatMessage.objects.filter(user=user).order_by('-timestamp')[:10]
        history = []
        for msg in reversed(recent):
            history.append({'author': 'user', 'content': msg.user_input})
            history.append({'author': 'assistant', 'content': msg.bot_response})

        # Add system prompt if new user
        if not recent.exists():
            history.insert(0, {'author': 'system', 'content': SYSTEM_PROMPT})

        # Process using your existing logic
        lower = transcript.lower()
        
        if lower in GREETINGS:
            bot_text = "Hello, welcome to Finda! What can we help you find today?"
        elif any(word in lower for word in THANKS):
            bot_text = "You're welcome! Let me know if you'd like to find anything else."
        elif any(pat in lower for pat in BROWSE_PATTERNS):
            categories = [display for key, display in Category.CATEGORY_CHOICES if key != 'all']
            bot_text = (
                "Sure! Here are some categories you can explore:\n" +
                "\n".join(f"- {cat}" for cat in categories) +
                "\n\nOr just tell me what you're looking for!"
            )
        else:
            # Your existing search logic
            prod_qs = Products.objects.filter(
                Q(product_name__icontains=transcript) |
                Q(product_description__icontains=transcript) |
                Q(product_brand__icontains=transcript),
                product_status='published'
            )
            serv_qs = Services.objects.filter(
                Q(service_name__icontains=transcript) |
                Q(service_description__icontains=transcript),
                service_status='published'
            )

            matches = list(prod_qs) + list(serv_qs)
            matches.sort(key=lambda obj: obj.average_rating(), reverse=True)

            if matches:
                top3 = matches[:3]
                response_lines = ["I found these on Finda:"]
                for obj in top3:
                    url = getattr(obj, 'get_absolute_url', lambda: f'/products/{obj.pk}/')()
                    price = getattr(obj, 'product_price', getattr(obj, 'service_price', 'N/A'))
                    response_lines.append(f"- {obj} — ₦{price}")
                response_lines.append("Would you also like suggestions from external stores?")
                bot_text = "\n".join(response_lines)
            else:
                bot_text = send_to_gemini(history, transcript)
        
        # Generate voice response if enabled
        voice_response_url = None
        if voice_enabled:
            language = voice_settings.preferred_language if voice_settings else 'en'
            slow_speech = voice_settings.voice_speed < 1.0 if voice_settings else False
            voice_response_url = generate_voice_response(bot_text, language, slow_speech)
        
        # Save conversation with voice metadata
        chat_message = ChatMessage.objects.create(
            user=user,
            user_input=transcript,
            bot_response=bot_text,
            is_voice_message=True,
            audio_file=audio_file,
            transcript=transcript,
            voice_response_url=voice_response_url or ""
        )
        
        return Response({
            "transcript": transcript,
            "reply": bot_text,
            "voice_response_url": voice_response_url,
            "message_id": chat_message.id
        })
        
    except Exception as e:
        return Response({"error": f"Voice processing failed: {str(e)}"}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def image_search_api(request):
    """NEW: Handle image searches"""
    if 'image' not in request.FILES:
        return Response({"error": "No image provided"}, status=400)
    
    image_file = request.FILES['image']
    user_query = request.data.get('query', 'What products are in this image?')
    user = request.user
    
    try:
        # Analyze image with Gemini Vision
        image_analysis = analyze_image_with_gemini(image_file, user_query)
        
        # Try to search your database using analysis results
        products = search_products_by_analysis(image_analysis, limit=3)
        
        if products:
            # Format response similar to your text search
            response_lines = ["Based on your image, I found these on Finda:"]
            for obj in products:
                url = getattr(obj, 'get_absolute_url', lambda: f'/products/{obj.pk}/')()
                price = getattr(obj, 'product_price', getattr(obj, 'service_price', 'N/A'))
                response_lines.append(f"- {obj} — ₦{price}\n  Link: https://yourdomain.com{url}")
            response_lines.append(
                "\nWould you also like suggestions from external stores based on this image?"
            )
            bot_text = "\n".join(response_lines)
        else:
            # No local matches - use Gemini's analysis as the response
            bot_text = image_analysis
        
        # Save conversation with image metadata
        chat_message = ChatMessage.objects.create(
            user=user,
            user_input=user_query,
            bot_response=bot_text,
            is_image_message=True,
            image_file=image_file,
            image_analysis=image_analysis
        )
        
        return Response({
            "image_analysis": image_analysis,
            "reply": bot_text,
            "local_products_found": len(products),
            "message_id": chat_message.id
        })
        
    except Exception as e:
        return Response({"error": f"Image processing failed: {str(e)}"}, status=500)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def voice_settings_api(request):
    """NEW: Manage user voice settings"""
    user = request.user
    
    if request.method == 'GET':
        settings, created = UserVoiceSettings.objects.get_or_create(user=user)
        serializer = VoiceSettingsSerializer(settings)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        settings, created = UserVoiceSettings.objects.get_or_create(user=user)
        serializer = VoiceSettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)