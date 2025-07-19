from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model

from .gemini_client import send_to_gemini
from .models import ChatMessage
from .serializers import ChatMessageSerializer
from main.models import Products, Services, LocationCategory  # Adjust if needed

User = get_user_model()
# — SYSTEM PROMPT (used on first message only) —
SYSTEM_PROMPT = (
    "You are the Finda shopping assistant. "
    "Greet the user: 'Hello, welcome to Finda! What can we help you find today?' "
    "When the user asks for a product or service, first search Finda's database. "
    "If matches exist, list the top 3 by rating and then ask: "
    "'Would you also like suggestions from external stores (Amazon, Jumia, etc.)?' "
    "If no matches, intelligently suggest alternatives using external sources."
)

# Intent dictionaries
GREETINGS = GREETINGS = {
    # English (General + Slang)
    "hi", "hello", "hey", "hiya", "yo", "howdy", "sup", "what's up", "hey there", "g'day", "how’s it going",
    "good morning", "good afternoon", "good evening", "evening", "morning", "good day",

    # French
    "bonjour", "salut", "bonsoir",

    # Spanish
    "hola", "buenos días", "buenas tardes", "buenas noches",

    # German
    "hallo", "guten tag", "guten morgen", "guten abend", "servus", "moin",

    # Italian
    "ciao", "buongiorno", "buonasera",

    # Portuguese
    "olá", "bom dia", "boa tarde", "boa noite",

    # Dutch
    "hallo", "goede dag", "goedemorgen", "goedenavond",

    # Russian
    "привет", "здравствуйте", "доброе утро", "добрый день", "добрый вечер",

    # Arabic
    "مرحبا", "اهلا", "السلام عليكم", "صباح الخير", "مساء الخير",

    # Chinese (Mandarin)
    "你好", "您好", "早上好", "下午好", "晚上好",

    # Japanese
    "こんにちは", "おはよう", "おはようございます", "こんばんは",

    # Korean
    "안녕하세요", "안녕", "좋은 아침", "좋은 저녁",

    # Hindi / Urdu
    "नमस्ते", "नमस्कार", "सुप्रभात", "शुभ संध्या", "ہیلو", "سلام", "آداب",

    # Yoruba (Nigeria)
    "ẹ n lẹ", "bawo ni", "kaaro", "kaasan", "kaale",

    # Igbo (Nigeria)
    "ndewo", "ututu oma", "ehihie oma", "mgbede oma",

    # Hausa (Nigeria)
    "sannu", "ina kwana", "ina wuni", "barka da safiya", "barka da rana", "barka da yamma",

    # Swahili (East Africa)
    "habari", "hujambo", "salama", "shikamoo", "asubuhi njema", "jioni njema",

    # Filipino / Tagalog
    "kamusta", "magandang umaga", "magandang hapon", "magandang gabi",

    # Turkish
    "merhaba", "selam", "günaydın", "iyi akşamlar",

    # Malay / Indonesian
    "selamat pagi", "selamat siang", "selamat sore", "selamat malam", "hai", "halo",

    # Greek
    "γεια", "γεια σου", "καλημέρα", "καλησπέρα",

    # Hebrew
    "שלום", "בוקר טוב", "ערב טוב",

    # Thai
    "สวัสดี", "สวัสดีครับ", "สวัสดีค่ะ",

    # Vietnamese
    "xin chào", "chào bạn", "chào buổi sáng", "chào buổi tối",

    # Bengali
    "হ্যালো", "নমস্কার", "সুপ্রভাত", "শুভ সন্ধ্যা",

    # Polish
    "cześć", "dzień dobry", "dobry wieczór",

    # Slang variations (English/Internet)
    "yo yo", "hey hey", "hi there", "wassup", "holla", "greetings", "peace", "yo fam", "what’s good", "how’s life",
}

THANKS = THANKS = {
    # English (Standard & Slang)
    "thanks", "thank you", "thanks a lot", "thank you so much", "thanks so much",
    "many thanks", "much appreciated", "cheers", "thanks a ton", "thank you kindly",
    "thx", "ty", "tysm", "tnx", "tq", "appreciate it", "thank u", "big thanks", "thanx", "tanks",

    # French
    "merci", "merci beaucoup", "grand merci",

    # Spanish
    "gracias", "muchas gracias", "mil gracias",

    # German
    "danke", "vielen dank", "danke schön", "tausend dank",

    # Italian
    "grazie", "mille grazie", "grazie mille",

    # Portuguese
    "obrigado", "obrigada", "muito obrigado", "muito obrigada",

    # Dutch
    "dank je", "dank je wel", "bedankt", "hartelijk dank",

    # Russian
    "спасибо", "большое спасибо", "спасибки",

    # Arabic
    "شكرا", "شكراً جزيلاً", "ألف شكر",

    # Chinese (Mandarin)
    "谢谢", "谢谢你", "多谢", "非常感谢",

    # Japanese
    "ありがとう", "ありがとうございます", "どうもありがとう", "感謝します",

    # Korean
    "감사합니다", "고맙습니다", "고마워", "감사해요",

    # Hindi / Urdu
    "धन्यवाद", "शुक्रिया", "बहुत धन्यवाद", "तहे दिल से शुक्रिया", "شکریہ", "بہت شکریہ",

    # Yoruba (Nigeria)
    "ẹ se", "ẹ ṣé púpọ̀", "o se", "o seun",

    # Igbo (Nigeria)
    "daalụ", "imeela", "ekele diri gị",

    # Hausa (Nigeria)
    "na gode", "nagode sosai",

    # Swahili (East Africa)
    "asante", "asante sana", "nashukuru", "ahsante",

    # Tagalog / Filipino
    "salamat", "maraming salamat", "salamat po",

    # Turkish
    "teşekkür ederim", "çok teşekkürler", "sağ olun",

    # Malay / Indonesian
    "terima kasih", "banyak terima kasih", "makasih", "trimakasih",

    # Greek
    "ευχαριστώ", "ευχαριστώ πολύ",

    # Hebrew
    "תודה", "תודה רבה",

    # Vietnamese
    "cảm ơn", "cảm ơn nhiều", "xin cảm ơn",

    # Thai
    "ขอบคุณ", "ขอบคุณมาก", "ขอบใจ",

    # Bengali
    "ধন্যবাদ", "অনেক ধন্যবাদ",

    # Polish
    "dziękuję", "dzięki", "wielkie dzięki",

    # Slang / Internet
    "tyvm", "tanks", "tx", "tqvm", "preciate it", "thanksy", "tyty", "10q", "thx a lot", "txs"
}

POSITIVE_CONFIRMATIONS = {
    # English (Standard & Slang)
    "yes", "yeah", "yep", "yup", "yah", "ya", "sure", "sure thing", "absolutely", "definitely",
    "for sure", "of course", "okay", "ok", "okey", "okey dokey", "alright", "roger that",
    "affirmative", "you got it", "sounds good", "why not", "go ahead", "let’s do it",
    "let’s go", "please do", "yess", "yesss", "yea", "yuh", "bet", "ight", "100%", "on god",
    "aye", "hell yes", "hell yeah", "fo sho", "for real", "no doubt", "yup please",
    "yes please", "that would be great", "yes do", "yes sure", "yes it is", "yes i do",
    "do it", "do that", "go on", "i want that", "yes go ahead", "yes why not", "abso-friggin-lutely",

    # Internet/Text Slang
    "y", "yaas", "yaaas", "yaaaas", "yaa", "u bet", "u got it", "okie", "okies", "okok",
    "tysm yes", "k", "kk", "kkk", "fasho", "tru", "truuu", "legit", "yazzz",

    # French
    "oui", "bien sûr", "absolument", "d'accord", "ouais", "c'est bon", "okey",

    # Spanish
    "sí", "claro", "por supuesto", "vale", "cierto", "desde luego",

    # German
    "ja", "natürlich", "klar", "sicher", "auf jeden fall",

    # Italian
    "sì", "certamente", "ovviamente", "va bene", "d'accordo",

    # Portuguese
    "sim", "claro", "com certeza", "pois não", "certo",

    # Dutch
    "ja", "zeker", "natuurlijk", "oké", "tuurlijk",

    # Russian
    "да", "конечно", "безусловно", "ага",

    # Arabic
    "نعم", "أكيد", "طبعا", "تمام", "أجل", "ايوا",

    # Chinese (Mandarin)
    "是", "对", "好的", "没问题", "行", "当然",

    # Japanese
    "はい", "ええ", "そうです", "もちろん", "了解です",

    # Korean
    "네", "예", "그럼요", "물론이죠", "좋아요",

    # Hindi / Urdu
    "हाँ", "जी हाँ", "बिलकुल", "हां", "جی ہاں", "بالکل", "ہاں",

    # Yoruba (Nigeria)
    "bẹẹni", "bẹ́ẹ̀ ni", "ó dáa", "ko si wahala",

    # Igbo (Nigeria)
    "ee", "eh", "ọ dị mma", "ọ dị", "n'ezie",

    # Hausa (Nigeria)
    "eh", "e", "tabbas", "toh", "eh na'am",

    # Swahili
    "ndiyo", "bila shaka", "sawa", "ndio", "hakika",

    # Tagalog / Filipino
    "oo", "opo", "sige", "syempre", "oo naman",

    # Turkish
    "evet", "tabii", "elbette", "olur", "tamam",

    # Greek
    "ναι", "βεβαίως", "σίγουρα", "φυσικά",

    # Vietnamese
    "vâng", "dạ", "có", "đúng rồi", "chắc chắn",

    # Thai
    "ใช่", "แน่นอน", "โอเค", "ตกลง", "ได้เลย",

    # Polish
    "tak", "oczywiście", "pewnie", "jasne",

    # Other affirmatives
    "ye", "aye aye", "can do", "def", "ya sure", "right on", "indubitably"
}

NEGATIVE_CONFIRMATIONS = {
    # English (Standard + Slang)
    "no", "nope", "nah", "na", "not really", "not now", "maybe later", "not interested",
    "no thanks", "no thank you", "i'm good", "i’ll pass", "not today", "no need",
    "don’t bother", "don’t worry about it", "pass", "hard pass", "no way", "absolutely not",
    "not at all", "not anymore", "not now thanks", "please no", "not for now",
    "nope not now", "never", "i’m fine", "i'm okay", "no i don't", "i don't want",
    "i don't need", "nah i'm good", "i’m okay thanks", "im good fam", "i’m good fr",
    "leave it", "forget it", "cancel", "i’m done", "that’s all", "that’s enough",
    "not necessary", "maybe next time",

    # Internet Shortcuts
    "n", "nuh uh", "no ty", "no tnx", "nope lol", "nah fam", "nah bruh", "nvm", "idc", "idk no",

    # French
    "non", "pas maintenant", "non merci", "jamais", "aucune envie",

    # Spanish
    "no", "nunca", "no gracias", "tal vez después", "ahora no",

    # German
    "nein", "nicht jetzt", "kein interesse", "ne danke", "auf keinen fall",

    # Italian
    "no", "non ora", "no grazie", "mai", "non adesso",

    # Portuguese
    "não", "não agora", "sem interesse", "não obrigado", "talvez depois",

    # Dutch
    "nee", "niet nu", "nee dank je", "geen interesse",

    # Russian
    "нет", "не сейчас", "не надо", "никогда", "не хочу",

    # Arabic
    "لا", "مش الآن", "مش مهتم", "لا شكراً", "لا أريد", "مش لازم", "مستحيل",

    # Chinese (Mandarin)
    "不", "不是", "不用", "不要", "不可以", "不行", "没兴趣", "以后再说",

    # Japanese
    "いいえ", "結構です", "いりません", "今はいい", "結構ですありがとう", "遠慮します",

    # Korean
    "아니요", "괜찮아요", "필요없어요", "지금은 아니에요", "사양할게요",

    # Hindi / Urdu
    "नहीं", "अभी नहीं", "धन्यवाद नहीं", "कोई ज़रूरत नहीं", "नहीं चाहिए", "نہیں", "ابھی نہیں", "شکریہ نہیں",

    # Yoruba
    "rara", "rara o", "mi o fe", "ko ye mi", "ma fi sile", "ko to ye",

    # Igbo
    "mba", "mba o", "a gaghi", "enweghị m mmasị", "hapụ ya", "i kwughị",

    # Hausa
    "a'a", "ba yanzu ba", "bana so", "babu bukata", "a'a nagode",

    # Swahili
    "hapana", "sio sasa", "sitaki", "hapana asante", "hapana shukrani",

    # Filipino / Tagalog
    "hindi", "ayoko", "huwag", "salamat pero hindi", "hindi ngayon",

    # Turkish
    "hayır", "şimdi değil", "istemiyorum", "hayır teşekkürler", "asla",

    # Greek
    "όχι", "όχι τώρα", "δεν θέλω", "όχι ευχαριστώ",

    # Vietnamese
    "không", "không phải bây giờ", "không cần", "không muốn", "không cảm ơn",

    # Thai
    "ไม่", "ไม่ตอนนี้", "ไม่เอา", "ไม่สนใจ", "ไม่ขอบคุณ",

    # Polish
    "nie", "nie teraz", "nie dziękuję", "nie chcę",

    # Informal Global
    "nah mate", "nah bro", "no brother", "not rn", "nuh uh", "don’t feel like it"
}

BROWSE_PATTERNS = {
    # English – casual & formal
    "what do you have", "what you got", "what can i find", "show me what you have",
    "show me", "show products", "browse", "let me browse", "explore", "i want to explore",
    "browse your catalog", "see items", "see services", "see products", "what's available",
    "available items", "what are you offering", "check what you offer", "what are your offers",
    "open catalog", "list categories", "list services", "list products", "list items",
    "search all", "shop all", "shop now", "start shopping", "start browsing",
    "can i browse", "i want to see what's here", "display all", "view categories",
    "display your categories", "i want to check things out", "let me shop", "can i shop",
    "product categories", "services available", "explore items", "explore services",
    "let’s explore", "let’s shop", "i want to look around", "i want to window shop",
    "view catalog", "see your catalog", "check what you have", "go to marketplace",

    # Slang / informal
    "whatchu got", "lemme see stuff", "got anything cool?", "got something?", "any stuff?",
    "any items?", "what's popping", "hook me up", "gimme options", "gimme items",

    # Emoji-style / minimal
    "🛒", "🛍️", "shop", "shopping", "market", "marketplace",

    # French
    "je veux voir", "je veux parcourir", "parcourir", "parcourir les produits",
    "voir les produits", "qu’avez-vous", "affichez les catégories",

    # Spanish
    "mostrar productos", "ver productos", "ver servicios", "qué tienes",
    "enséñame lo que tienes", "explorar", "lista de categorías",

    # Portuguese
    "ver produtos", "o que você tem", "mostrar categorias", "explorar catálogo",
    "posso ver tudo", "mostrar itens", "listar serviços", "navegar",

    # German
    "was hast du", "zeige produkte", "katalog anzeigen", "durchstöbern", "ich möchte stöbern",

    # Dutch
    "laat me zien", "wat heb je", "bekijk producten", "categorielijst", "verkennen",

    # Italian
    "cosa avete", "fammi vedere", "mostra prodotti", "naviga", "sfoglia il catalogo",

    # Arabic
    "ما الذي لديك", "عرض المنتجات", "أرني", "أريد التصفح", "عرض الفئات", "استعراض",

    # Yoruba
    "ki ni e ni", "fi ohun ti e ni han", "mo fe ra nkan", "fi gbogbo nkan han mi",

    # Hausa
    "me kake da shi", "ina son gani", "bari in duba", "nemi kaya", "bude kasuwa",

    # Igbo
    "gini ka i nwere", "chọpụtara", "gosi m ihe dị", "m chọrọ ile anya", "leekwa ihe unu nwere",

    # Swahili
    "nionyeshe bidhaa", "naweza kuvinjari", "ninaweza kuona", "onyesha bidhaa zako", "angalia maduka",

    # Hindi / Urdu
    "क्या है आपके पास", "मुझे दिखाओ", "सभी उत्पाद देखें", "کیا ہے تمہارے پاس", "مجھے دکھاو",

    # Chinese (Mandarin)
    "你有什么", "浏览产品", "展示所有产品", "我想看", "打开目录",

    # Japanese
    "何がありますか", "商品を見せて", "カタログを見せて", "ブラウズしたい",

    # Korean
    "뭐 있어요?", "상품 보여줘", "목록 보여줘", "구경할래요",

    # Vietnamese
    "bạn có gì", "xem sản phẩm", "duyệt danh mục", "mở danh mục",

    # Tagalog / Filipino
    "ano meron ka", "ipakita ang produkto", "tingnan ang mga item", "browse ko lang",

    # Turkish
    "ne var", "ürünleri göster", "kategorilere bakmak istiyorum", "kataloğu aç",

    # Misc friendly
    "recommend something", "i’m curious", "just looking", "let me see what you have", "anything to check out?"
}

class CustomAuthToken(APIView):
    permission_classes = [AllowAny]  # ✅ Important
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
                # Add more user fields if needed
            }
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_api(request):
    user = request.user
    raw_message = request.data.get('message', '').strip()
    if not raw_message:
        return Response({"detail": "Please send a non-empty message."}, status=400)
    lower = raw_message.lower()

    # 1) Chat history
    recent = ChatMessage.objects.filter(user=user).order_by('-timestamp')[:10]
    history = []
    for msg in reversed(recent):
        history.append({'author': 'user', 'content': msg.user_input})
        history.append({'author': 'assistant', 'content': msg.bot_response})

    # 2) Add system prompt if new user
    if not recent.exists():
        history.insert(0, {'author': 'system', 'content': SYSTEM_PROMPT})

    try:
        # 3) Intent: Greeting
        if lower in GREETINGS:
            bot_text = "Hello, welcome to Finda! What can we help you find today?"

        # 4) Intent: Thank-you
        elif any(word in lower for word in THANKS):
            bot_text = "You're welcome! Let me know if you’d like to find anything else."

        # 5) Intent: Browse categories
        elif any(pat in lower for pat in BROWSE_PATTERNS):
            categories = [display for key, display in LocationCategory.CATEGORY_CHOICES if key != 'all']
            bot_text = (
                "Sure! Here are some categories you can explore:\n" +
                "\n".join(f"- {cat}" for cat in categories) +
                "\n\nOr just type in what you're looking for (e.g., 'Nike shoes', 'barber services')."
            )

        else:
            # 6) Check if previous message offered external suggestions
            last_bot_msg = history[-1]['content'].lower() if history and history[-1]['author'] == 'assistant' else ""
            asked_external = "external stores" in last_bot_msg

            # 7) Positive reply → Use Gemini
            if asked_external and any(word in lower for word in POSITIVE_CONFIRMATIONS):
                bot_text = send_to_gemini(history, raw_message)

            # 8) Negative → Proceed with new query
            elif asked_external and any(word in lower for word in NEGATIVE_CONFIRMATIONS):
                raise ValueError("Restarting DB search...")

            else:
                # 9) Search Finda database first
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
                    # 10) No DB match → use Gemini automatically
                    bot_text = send_to_gemini(history, raw_message)
    except Exception:
        # 11) Final fallback
        bot_text = send_to_gemini(history, raw_message)
    # 12) Save conversation
    ChatMessage.objects.create(
        user=user,
        user_input=raw_message,
        bot_response=bot_text
    )
    return Response({"reply": bot_text})
