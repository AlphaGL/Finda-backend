"""
Optimized Django settings for Ecommerce + Chatbot Backend on Render
"""
import os
from pathlib import Path
from decouple import config
import dj_database_url
from dotenv import load_dotenv
from corsheaders.defaults import default_headers

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Render environment detection
IS_RENDER = os.environ.get('RENDER') == 'true'

# cloudinary imports
import cloudinary
import cloudinary.uploader
import cloudinary.api

TEMPLATES_DIRS = os.path.join(BASE_DIR, 'templates')

# Security settings
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)

# Optimized allowed hosts
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'finda-backend.onrender.com',
    '.onrender.com',
] if not DEBUG else ['*']

# Application definition - optimized for ecommerce + chatbot
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # My apps
    'main.apps.MainConfig',        # Ecommerce logic
    'users.apps.UsersConfig',      # User management
    'chatbot',                     # Chatbot functionality

    # Ecommerce essentials
    'django_countries',            # Country fields for shipping
    'django_filters',              # Product filtering
    'corsheaders',                 # API access
    # 'mptt',                        # Category hierarchies
    # 'taggit',                      # Product tags

    # Background tasks for order processing & chatbot
    'django_celery_beat',
    'django_celery_results',

    # File storage for product images
    'cloudinary',
    'cloudinary_storage',

    # Authentication (customers, vendors)
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    
    # API framework
    'rest_framework',
    'rest_framework.authtoken',
]

SITE_ID = 1

# ===========================
#  ECOMMERCE CONFIGURATION
# ===========================

# Product settings
PRODUCTS_PER_PAGE = 20
MAX_CART_ITEMS = 100
CURRENCY = 'NGN'  # Nigerian Naira
SHIPPING_COST_THRESHOLD = 50000  # Free shipping above 50k NGN

# ===========================
#  CHATBOT CONFIGURATION
# ===========================

# Google AI (Gemini) Configuration for chatbot
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', config('GOOGLE_API_KEY', default=''))

# Enhanced chatbot prompt for ecommerce
CHAT_SYSTEM_PROMPT = """
You are Finda's AI shopping assistant for our ecommerce platform. Your role:

1. Welcome users warmly: "Hello! Welcome to Finda! I'm here to help you find the perfect products. What are you looking for today?"

2. Product Search Strategy:
   - First search our Finda product database for matches
   - Show top 3 results with: name, price, rating, brief description
   - Ask: "Would you like me to find similar items from other stores too?"
   - If no local matches, search external sources (Amazon, Jumia, Konga)

3. Shopping Assistance:
   - Help with product comparisons
   - Suggest alternatives and similar products
   - Provide size/color/variant information
   - Help with order tracking queries
   - Answer shipping and return policy questions

4. Voice & Image Support:
   - Process voice messages for hands-free shopping
   - Analyze product images users send for identification

Keep responses helpful, concise, and sales-focused while being genuinely helpful.
"""

# ===========================
#  DATABASE OPTIMIZATION
# ===========================

DATABASES = {
    'default': {
        **dj_database_url.parse(
            config('DATABASE_URL', default='postgresql://postgres.ozehxqqzrlkrbqeoiddq:finda_db_2@aws-0-eu-north-1.pooler.supabase.com:6543/postgres')
        ),
        'CONN_MAX_AGE': 60,  # Connection pooling
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {
            'connect_timeout': 10,
            'options': '-c statement_timeout=30s -c idle_in_transaction_session_timeout=30s'
        }
    }
}

# Redis cache for cart, sessions, and chatbot responses
REDIS_URL = os.environ.get("REDIS_URL")
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
        'KEY_PREFIX': 'finda',
        'TIMEOUT': 3600,  # 1 hour default
        'OPTIONS': {
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 25,
                'retry_on_timeout': True,
                'health_check_interval': 30,
            },
        }
    }
}

# Cache timeouts for different data
CACHE_TIMEOUTS = {
    'products': 1800,      # 30 minutes for product data
    'categories': 3600,    # 1 hour for categories
    'cart': 86400,         # 24 hours for cart data
    'chatbot': 1800,       # 30 minutes for chatbot responses
    'search': 900,         # 15 minutes for search results
}

# ===========================
#  API CONFIGURATION
# ===========================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '1000/hour',      # Higher for browsing products
        'user': '3000/hour',      # Higher for authenticated users
        'chatbot': '2000/hour',   # High limit for chatbot interactions
        'search': '500/hour',     # Reasonable limit for search
        'checkout': '100/hour',   # Conservative for payments
    },
}

# Authentication Configuration
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
SOCIALACCOUNT_ADAPTER = 'users.adapters.CustomSocialAccountAdapter'

# ===========================
#  FILE STORAGE
# ===========================

# Cloudinary for product images, user avatars, chatbot media
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': config('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': config('CLOUDINARY_API_KEY'),
    'API_SECRET': config('CLOUDINARY_API_SECRET'),
    'SECURE': True,
}

cloudinary.config( 
    cloud_name=config('CLOUDINARY_CLOUD_NAME'), 
    api_key=config('CLOUDINARY_API_KEY'), 
    api_secret=config('CLOUDINARY_API_SECRET') 
)

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
CLOUDINARY_URL = config('CLOUDINARY_URL')

# ===========================
#  MIDDLEWARE OPTIMIZATION
# ===========================

MIDDLEWARE = [
    # Security first
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    
    # Static files
    'whitenoise.middleware.WhiteNoiseMiddleware',
    
    # Core Django middleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # Authentication
    "allauth.account.middleware.AccountMiddleware",
]

# ===========================
#  CORS & SECURITY
# ===========================

CSRF_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",      # React frontend
    "http://localhost:5173",      # Vite frontend
    "https://finda-six.vercel.app",
    "https://finda-api-chatbot.vercel.app",
]

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "https://finda-six.vercel.app",
    "https://finda-api-chatbot.vercel.app",
] if not DEBUG else []

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(default_headers) + [
    "authorization",
    "x-csrftoken",
]

# ===========================
#  PAYMENT CONFIGURATION
# ===========================

# Paystack (Primary for Nigerian market)
PAYSTACK_SECRET_KEY = config('PAYSTACK_SECRET_KEY')
PAYSTACK_PUBLIC_KEY = config('PAYSTACK_PUBLIC_KEY')
PAYSTACK_PAYMENT_URL = 'https://api.paystack.co/transaction/initialize'

# Stripe (For international customers)
STRIPE_PUBLIC_KEY = config('STRIPE_PUBLIC_KEY', default='')
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY', default='')

# Google OAuth for easy customer login
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': config('CLIENT_ID'),
            'secret': config('SECRET'),
            'key': ''
        }
    }
}

ROOT_URLCONF = 'master.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [TEMPLATES_DIRS],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'master.wsgi.application'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTH_USER_MODEL = 'users.CustomUser'
AUTHENTICATION_BACKENDS = [
    'users.auth_backends.EmailOrPhoneBackend',
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'  # Nigerian timezone
USE_I18N = True
USE_TZ = True

LOGIN_REDIRECT_URL = '/'

# ===========================
#  EMAIL CONFIGURATION
# ===========================

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 465
EMAIL_USE_SSL = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = config('EMAIL_HOST_USER')

# ===========================
#  FILE UPLOAD SETTINGS
# ===========================

# Product images, chatbot media
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024   # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024   # 5MB
IMAGE_MAX_SIZE = 3 * 1024 * 1024   # 3MB for product images

# ===========================
#  BACKGROUND TASKS (CELERY)
# ===========================

# For order processing, chatbot responses, email notifications
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Africa/Lagos'
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutes
CELERY_TASK_TIME_LIMIT = 600  # 10 minutes

# ===========================
#  STATIC FILES
# ===========================

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'main/static')
] if os.path.exists(os.path.join(BASE_DIR, 'main/static')) else []
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# WhiteNoise for static files
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
WHITENOISE_USE_FINDERS = not IS_RENDER
WHITENOISE_AUTOREFRESH = not IS_RENDER
WHITENOISE_MAX_AGE = 31536000 if IS_RENDER else 0

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ===========================
#  EXTERNAL API CONFIGURATION
# ===========================

# SerpAPI for external product search (when chatbot can't find local products)
SERPAPI_CONFIG = {
    'ENABLED': True,
    'API_KEY': config('SERPAPI_KEY', default='7e724f18b98b7b44714da50a198ddc2ca5fe92b051a0cd51f129c3887a0893f6'),
    'TIMEOUT': 10,  # Reasonable timeout
    'MAX_RESULTS': 5,  # Focused results
    'DEFAULT_LOCATION': 'Nigeria'
}

# ===========================
#  CHATBOT OPTIMIZATION
# ===========================

CHATBOT_SETTINGS = {
    'EXTERNAL_SEARCH_ENABLED': True,
    'MIN_LOCAL_RESULTS_THRESHOLD': 2,  # Search external if < 2 local results
    'MAX_EXTERNAL_RESULTS': 5,
    'SEARCH_CACHE_TIMEOUT': 1800,  # 30 minutes
    'DEFAULT_SEARCH_STRATEGY': 'hybrid_local_first',  # Prioritize our products
    'ENABLE_CONCURRENT_SEARCH': True,  # Faster responses
    'REQUEST_TIMEOUT': 10,
    'VOICE_RESPONSE_ENABLED': True,
    'IMAGE_RECOGNITION_ENABLED': True,
    'MAX_CONVERSATION_HISTORY': 10,  # Keep last 10 messages for context
}

# ===========================
#  SEARCH CONFIGURATION
# ===========================

# Product search settings
SEARCH_SETTINGS = {
    'MIN_QUERY_LENGTH': 2,
    'MAX_RESULTS_PER_PAGE': 50,
    'ENABLE_FUZZY_SEARCH': True,
    'SEARCH_FIELDS': [
        'name', 'description', 'tags__name', 
        'category__name', 'brand'
    ],
    'BOOST_FIELDS': {
        'name': 2.0,
        'tags__name': 1.5,
    }
}

# ===========================
#  LOGGING
# ===========================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO' if IS_RENDER else 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'chatbot': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'ecommerce': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django': {
            'handlers': ['console'],
            'level': 'WARNING' if IS_RENDER else 'INFO',
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

# ===========================
#  SESSION & SECURITY
# ===========================

# Shopping cart and user sessions
SESSION_COOKIE_AGE = 86400 * 7  # 1 week for shopping cart persistence
SESSION_SAVE_EVERY_REQUEST = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG

# Security settings
if IS_RENDER or not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    X_FRAME_OPTIONS = 'DENY'

# ===========================
#  PERFORMANCE OPTIMIZATION
# ===========================

# Cache pages for better performance
CACHE_MIDDLEWARE_ALIAS = 'default'
CACHE_MIDDLEWARE_SECONDS = 300  # 5 minutes for product pages
CACHE_MIDDLEWARE_KEY_PREFIX = 'finda'

# Database query optimization
DATABASE_ROUTERS = []  # Add custom routers if needed for read/write splitting