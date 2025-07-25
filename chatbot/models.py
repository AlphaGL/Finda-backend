# chatbot/models.py - Enhanced Models with Advanced Features
from django.conf import settings
from django.db import models
from cloudinary.models import CloudinaryField
import uuid

class ChatSession(models.Model):
    """Chat session to group related messages"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions"
    )
    title = models.CharField(max_length=255, blank=True, null=True)
    preference_data = models.JSONField(default=dict, blank=True)
    awaiting_external_confirmation = models.BooleanField(default=False)
    last_search_query = models.TextField(blank=True, null=True)
    last_search_type = models.CharField(
        max_length=20,
        choices=[('product', 'Product'), ('service', 'Service')],
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        title = self.title or f"Session {self.id}"
        return f"{self.user.email} - {title}"

    @property
    def message_count(self):
        return self.messages.count()

    @property
    def last_message_time(self):
        last_message = self.messages.order_by('-timestamp').first()
        return last_message.timestamp if last_message else self.created_at


class ChatMessage(models.Model):
    """Enhanced chat message model with multimedia support"""
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text Message'),
        ('voice', 'Voice Message'),
        ('image', 'Image Message'),
    ]

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages"
    )
    user_input = models.TextField()
    bot_response = models.TextField()
    message_type = models.CharField(
        max_length=10,
        choices=MESSAGE_TYPE_CHOICES,
        default='text'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Voice message support
    audio_file = CloudinaryField('chat/audio', blank=True, null=True)
    transcription_confidence = models.FloatField(blank=True, null=True)
    
    # Image message support
    image_file = CloudinaryField('chat/images', blank=True, null=True)
    image_analysis_data = models.JSONField(default=dict, blank=True)
    
    # Conversation context
    preference_data = models.JSONField(default=dict, blank=True)
    search_results_data = models.JSONField(default=dict, blank=True)
    external_sources_offered = models.BooleanField(default=False)
    
    # Performance metrics
    response_time_ms = models.PositiveIntegerField(blank=True, null=True)
    user_feedback = models.CharField(
        max_length=20,
        choices=[
            ('helpful', 'Helpful'),
            ('not_helpful', 'Not Helpful'),
            ('partial', 'Partially Helpful')
        ],
        blank=True,
        null=True
    )

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['session', 'timestamp']),
            models.Index(fields=['message_type']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        session_title = self.session.title or f"Session {self.session.id}"
        return f"{self.timestamp:%Y-%m-%d %H:%M} | {session_title}: {self.user_input[:50]}"

    @property
    def has_multimedia(self):
        return bool(self.audio_file or self.image_file)


class UserPreference(models.Model):
    """Store user preferences for better personalization"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_preferences"
    )
    
    # Shopping preferences
    preferred_categories = models.JSONField(default=list, blank=True)
    preferred_price_range = models.JSONField(default=dict, blank=True)  # {'min': 0, 'max': 1000}
    preferred_locations = models.JSONField(default=list, blank=True)
    preferred_brands = models.JSONField(default=list, blank=True)
    
    # Communication preferences
    preferred_language = models.CharField(max_length=10, default='en')
    voice_enabled = models.BooleanField(default=True)
    image_search_enabled = models.BooleanField(default=True)
    external_sources_preference = models.CharField(
        max_length=20,
        choices=[
            ('always', 'Always Show'),
            ('ask', 'Ask Each Time'),
            ('never', 'Never Show')
        ],
        default='ask'
    )
    
    # AI behavior preferences
    response_style = models.CharField(
        max_length=20,
        choices=[
            ('brief', 'Brief and Direct'),
            ('detailed', 'Detailed and Explanatory'),
            ('casual', 'Casual and Friendly')
        ],
        default='casual'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences for {self.user.email}"


class SearchQuery(models.Model):
    """Track search queries for analytics and improvement"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="search_queries"
    )
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="search_queries",
        null=True,
        blank=True
    )
    
    original_query = models.TextField()
    processed_query = models.TextField(blank=True, null=True)
    search_type = models.CharField(
        max_length=20,
        choices=[('product', 'Product'), ('service', 'Service'), ('mixed', 'Mixed')],
        default='mixed'
    )
    
    # Results
    internal_results_count = models.PositiveIntegerField(default=0)
    external_sources_requested = models.BooleanField(default=False)
    
    # User interaction
    result_clicked = models.BooleanField(default=False)
    user_satisfied = models.BooleanField(null=True, blank=True)
    
    # Metadata
    preferences_used = models.JSONField(default=dict, blank=True)
    response_time_ms = models.PositiveIntegerField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['search_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Search: {self.original_query[:50]}"


class ProductSuggestion(models.Model):
    """Store AI-generated product suggestions for tracking accuracy"""
    search_query = models.ForeignKey(
        SearchQuery,
        on_delete=models.CASCADE,
        related_name="suggestions"
    )
    
    # Internal product (if matched)
    internal_product = models.ForeignKey(
        'main.Products',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ai_suggestions"
    )
    
    # External suggestion data
    external_data = models.JSONField(default=dict, blank=True)
    
    # Suggestion metrics
    rank_position = models.PositiveIntegerField()
    confidence_score = models.FloatField(blank=True, null=True)
    user_clicked = models.BooleanField(default=False)
    user_rating = models.PositiveIntegerField(
        blank=True, 
        null=True,
        choices=[(i, str(i)) for i in range(1, 6)]  # 1-5 rating
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['rank_position']
        indexes = [
            models.Index(fields=['search_query', 'rank_position']),
            models.Index(fields=['user_clicked']),
        ]

    def __str__(self):
        if self.internal_product:
            return f"Internal: {self.internal_product.product_name}"
        return f"External: {self.external_data.get('name', 'Unknown')}"


class VoiceMessage(models.Model):
    """Separate model for detailed voice message handling"""
    chat_message = models.OneToOneField(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="voice_details"
    )
    
    # Audio processing details
    original_duration_seconds = models.FloatField(blank=True, null=True)
    file_size_bytes = models.PositiveIntegerField(blank=True, null=True)
    audio_format = models.CharField(max_length=20, blank=True, null=True)
    sample_rate = models.PositiveIntegerField(blank=True, null=True)
    
    # Transcription details
    transcription_engine = models.CharField(
        max_length=50,
        choices=[
            ('google', 'Google Speech-to-Text'),
            ('whisper', 'OpenAI Whisper'),
            ('azure', 'Azure Speech Services'),
        ],
        default='google'
    )
    transcription_confidence = models.FloatField(blank=True, null=True)
    language_detected = models.CharField(max_length=10, blank=True, null=True)
    
    # Processing metrics
    processing_time_ms = models.PositiveIntegerField(blank=True, null=True)
    transcription_attempts = models.PositiveIntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Voice message from {self.chat_message.session.user.email}"


class ImageAnalysis(models.Model):
    """Detailed image analysis results"""
    chat_message = models.OneToOneField(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="image_details"
    )
    
    # Image processing details
    original_width = models.PositiveIntegerField(blank=True, null=True)
    original_height = models.PositiveIntegerField(blank=True, null=True)
    file_size_bytes = models.PositiveIntegerField(blank=True, null=True)
    image_format = models.CharField(max_length=20, blank=True, null=True)
    
    # AI analysis results
    detected_objects = models.JSONField(default=list, blank=True)
    detected_text = models.TextField(blank=True, null=True)
    dominant_colors = models.JSONField(default=list, blank=True)
    
    # Product identification
    product_category_detected = models.CharField(max_length=100, blank=True, null=True)
    brand_detected = models.CharField(max_length=100, blank=True, null=True)
    product_attributes = models.JSONField(default=dict, blank=True)
    
    # Analysis confidence
    overall_confidence = models.FloatField(blank=True, null=True)
    analysis_engine = models.CharField(
        max_length=50,
        choices=[
            ('gemini', 'Google Gemini Vision'),
            ('gpt4v', 'GPT-4 Vision'),
            ('azure', 'Azure Computer Vision'),
        ],
        default='gemini'
    )
    
    # Processing metrics
    processing_time_ms = models.PositiveIntegerField(blank=True, null=True)
    analysis_attempts = models.PositiveIntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image analysis for {self.chat_message.session.user.email}"


class ConversationContext(models.Model):
    """Track conversation context and state"""
    session = models.OneToOneField(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="context"
    )
    
    # Current conversation state
    current_intent = models.CharField(
        max_length=50,
        choices=[
            ('greeting', 'Greeting'),
            ('browsing', 'Browsing Categories'),
            ('searching', 'Searching Products/Services'),
            ('filtering', 'Refining Search'),
            ('comparing', 'Comparing Options'),
            ('external_confirm', 'Confirming External Sources'),
            ('completed', 'Search Completed'),
        ],
        default='greeting'
    )
    
    # Conversation flow
    questions_asked = models.JSONField(default=list, blank=True)
    preferences_collected = models.JSONField(default=dict, blank=True)
    missing_preferences = models.JSONField(default=list, blank=True)
    
    # Search state
    last_search_results_internal = models.JSONField(default=list, blank=True)
    last_search_results_external = models.JSONField(default=list, blank=True)
    external_sources_shown = models.BooleanField(default=False)
    
    # User behavior tracking
    bounce_count = models.PositiveIntegerField(default=0)  # Times user changed topic
    refinement_count = models.PositiveIntegerField(default=0)  # Times user refined search
    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Context for {self.session}"


class FeedbackRating(models.Model):
    """User feedback on chat interactions"""
    chat_message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="feedback_ratings"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    
    # Rating categories
    helpfulness_rating = models.PositiveIntegerField(
        choices=[(i, str(i)) for i in range(1, 6)],
        help_text="How helpful was this response? (1-5)"
    )
    accuracy_rating = models.PositiveIntegerField(
        choices=[(i, str(i)) for i in range(1, 6)],
        blank=True,
        null=True,
        help_text="How accurate were the results? (1-5)"
    )
    response_speed_rating = models.PositiveIntegerField(
        choices=[(i, str(i)) for i in range(1, 6)],
        blank=True,
        null=True,
        help_text="How was the response speed? (1-5)"
    )
    
    # Feedback text
    feedback_text = models.TextField(blank=True, null=True)
    
    # Issues reported
    issues_reported = models.JSONField(
        default=list,
        blank=True,
        help_text="List of issues: ['wrong_results', 'slow_response', 'unclear_answer', etc.]"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('chat_message', 'user')
        indexes = [
            models.Index(fields=['helpfulness_rating']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Feedback: {self.helpfulness_rating}/5 stars"


class ExternalSourceTracking(models.Model):
    """Track external source performance and reliability"""
    source_name = models.CharField(max_length=100)  # Amazon, Jumia, etc.
    
    # Performance metrics
    total_requests = models.PositiveIntegerField(default=0)
    successful_requests = models.PositiveIntegerField(default=0)
    average_response_time_ms = models.FloatField(blank=True, null=True)
    
    # User interaction
    click_through_rate = models.FloatField(default=0.0)
    user_satisfaction_score = models.FloatField(blank=True, null=True)
    
    # Reliability
    last_successful_request = models.DateTimeField(blank=True, null=True)
    consecutive_failures = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # Configuration
    api_endpoint = models.URLField(blank=True, null=True)
    api_key_required = models.BooleanField(default=False)
    rate_limit_per_hour = models.PositiveIntegerField(default=100)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-user_satisfaction_score', 'source_name']
        indexes = [
            models.Index(fields=['is_active', '-user_satisfaction_score']),
            models.Index(fields=['source_name']),
        ]

    def __str__(self):
        return f"{self.source_name} - {self.success_rate:.1%} success"

    @property
    def success_rate(self):
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests