# chatbot/__init__.py

# REMOVE ALL DJANGO/DRF IMPORTS FROM HERE
# These imports should only be in views.py and other modules, not in __init__.py

# This file should remain minimal during Django app loading
# All Django-related imports belong in the actual modules that use them

# If you need to configure the app, use apps.py instead

default_app_config = 'chatbot.apps.ChatbotConfig'