from django.apps import AppConfig

class ChatbotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chatbot'
    verbose_name = 'Chatbot'
    
    def ready(self):
        """
        Perform initialization tasks when the app is ready.
        This is called after all models have been loaded.
        """
        # Import signals or perform other initialization tasks here
        # Only import Django components here, after apps are loaded
        try:
            # Example: Import signals
            # from . import signals
            pass
        except ImportError:
            pass
        
        # Initialize any chatbot-specific configurations
        self.initialize_chatbot_services()
    
    def initialize_chatbot_services(self):
        """
        Initialize chatbot services after Django is fully loaded
        """
        try:
            # Initialize caching
            from django.core.cache import cache
            cache.set('chatbot_initialized', True, timeout=3600)
            
            # Initialize logging
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Chatbot app initialized successfully")
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Chatbot initialization error: {str(e)}")