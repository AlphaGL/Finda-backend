# ai_chatbot/models.py
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from cloudinary.models import CloudinaryField
import uuid
import json


class ChatSession(models.Model):
    """Main chat session model"""
    SESSION_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('ended', 'Ended'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='chat_sessions',
        null=True, 
        blank=True  # Allow anonymous users
    )
    session_id = models.CharField(max_length=100, unique=True)  # For anonymous users
    title = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(max_length=20, choices=SESSION_STATUS_CHOICES, default='active')
    
    # Session context and preferences
    user_preferences = models.JSONField(default=dict, blank=True)
    search_context = models.JSONField(default=dict, blank=True)
    location_context = models.JSONField(default=dict, blank=True)  # User's preferred location
    
    # Metadata
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    device_info = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['last_activity']),
        ]
    
    def __str__(self):
        if self.user:
            return f"Chat Session: {self.user.email} - {self.created_at.date()}"
        return f"Anonymous Chat: {self.session_id[:8]} - {self.created_at.date()}"
    
    def get_recent_messages(self, limit=10):
        return self.messages.filter(is_active=True).order_by('-created_at')[:limit]
    
    def update_activity(self):
        self.last_activity = models.DateTimeField(auto_now=True)
        self.save(update_fields=['last_activity'])


class ChatMessage(models.Model):
    """Individual chat messages"""
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text Message'),
        ('image', 'Image Message'),
        ('voice', 'Voice Message'),
        ('file', 'File Upload'),
        ('system', 'System Message'),
    ]
    
    SENDER_TYPE_CHOICES = [
        ('user', 'User'),
        ('bot', 'Bot'),
        ('system', 'System'),
    ]
    
    SEARCH_MODE_CHOICES = [
        ('local', 'Local Database Search'),
        ('external', 'External Web Search'),
        ('hybrid', 'Hybrid Search'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat_session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    
    # Message content
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default='text')
    sender_type = models.CharField(max_length=20, choices=SENDER_TYPE_CHOICES)
    content = models.TextField()  # Main message content
    
    # Media attachments
    image = CloudinaryField('chat/images', blank=True, null=True)
    voice_file = CloudinaryField('chat/voice', blank=True, null=True)
    attachment = CloudinaryField('chat/files', blank=True, null=True)
    
    # Bot response metadata
    search_mode = models.CharField(max_length=20, choices=SEARCH_MODE_CHOICES, blank=True, null=True)
    response_time = models.FloatField(blank=True, null=True)  # Response time in seconds
    confidence_score = models.FloatField(blank=True, null=True)  # AI confidence
    search_results_count = models.PositiveIntegerField(default=0)
    
    # Message context
    context_data = models.JSONField(default=dict, blank=True)  # Store search results, etc.
    intent_detected = models.CharField(max_length=100, blank=True, null=True)
    entities_extracted = models.JSONField(default=list, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_edited = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['chat_session', 'created_at']),
            models.Index(fields=['sender_type', 'message_type']),
            models.Index(fields=['intent_detected']),
        ]
    
    def __str__(self):
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"{self.sender_type}: {content_preview}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update session activity
        self.chat_session.update_activity()


class SearchQuery(models.Model):
    """Track search queries and results"""
    SEARCH_TYPE_CHOICES = [
        ('product', 'Product Search'),
        ('service', 'Service Search'),
        ('mixed', 'Mixed Search'),
        ('general', 'General Query'),
    ]
    
    SOURCE_CHOICES = [
        ('local_db', 'Local Database'),
        ('gemini_web', 'Gemini + Web Search'),
        ('both', 'Both Sources'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat_message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='search_queries')
    
    # Query details
    query_text = models.TextField()
    search_type = models.CharField(max_length=20, choices=SEARCH_TYPE_CHOICES)
    source_used = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    
    # Search parameters
    filters = models.JSONField(default=dict, blank=True)  # Category, location, price range, etc.
    location_context = models.JSONField(default=dict, blank=True)
    
    # Results
    local_results_count = models.PositiveIntegerField(default=0)
    external_results_count = models.PositiveIntegerField(default=0)
    total_results_shown = models.PositiveIntegerField(default=0)
    
    # Performance metrics
    search_duration = models.FloatField(blank=True, null=True)  # Search time in seconds
    success_rate = models.FloatField(blank=True, null=True)  # Success rate for external searches
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['search_type', 'created_at']),
            models.Index(fields=['source_used']),
        ]
    
    def __str__(self):
        return f"Search: {self.query_text[:30]}... ({self.search_type})"


class SearchResult(models.Model):
    """Store search results for analytics and caching"""
    RESULT_TYPE_CHOICES = [
        ('product', 'Product'),
        ('service', 'Service'),
        ('external_product', 'External Product'),
        ('information', 'Information/Answer'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    search_query = models.ForeignKey(SearchQuery, on_delete=models.CASCADE, related_name='results')
    
    # Result details
    result_type = models.CharField(max_length=20, choices=RESULT_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)
    
    # For local results (products/services)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, blank=True, null=True)
    object_id = models.PositiveIntegerField(blank=True, null=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # External result data
    external_data = models.JSONField(default=dict, blank=True)
    price_info = models.JSONField(default=dict, blank=True)
    location_info = models.JSONField(default=dict, blank=True)
    
    # Ranking and relevance
    relevance_score = models.FloatField(default=0.0)
    position = models.PositiveIntegerField()  # Position in results
    
    # User interactions
    click_count = models.PositiveIntegerField(default=0)
    was_clicked = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['position']
        indexes = [
            models.Index(fields=['search_query', 'position']),
            models.Index(fields=['result_type']),
            models.Index(fields=['relevance_score']),
        ]
    
    def __str__(self):
        return f"{self.title} (Position: {self.position})"


class UserFeedback(models.Model):
    """User feedback on bot responses"""
    FEEDBACK_TYPE_CHOICES = [
        ('thumbs_up', 'Thumbs Up'),
        ('thumbs_down', 'Thumbs Down'),
        ('rating', 'Rating (1-5)'),
        ('comment', 'Text Feedback'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat_message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='feedbacks')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True)
    
    # Feedback details
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPE_CHOICES)
    rating = models.PositiveSmallIntegerField(blank=True, null=True)  # 1-5 rating
    comment = models.TextField(blank=True, null=True)
    
    # Specific feedback areas
    accuracy_rating = models.PositiveSmallIntegerField(blank=True, null=True)
    helpfulness_rating = models.PositiveSmallIntegerField(blank=True, null=True)
    speed_rating = models.PositiveSmallIntegerField(blank=True, null=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['chat_message', 'user']  # One feedback per user per message
        indexes = [
            models.Index(fields=['feedback_type', 'created_at']),
            models.Index(fields=['rating']),
        ]
    
    def __str__(self):
        return f"Feedback: {self.feedback_type} for message {self.chat_message.id}"


class ChatAnalytics(models.Model):
    """Daily analytics for chatbot performance"""
    date = models.DateField(unique=True)
    
    # Usage metrics
    total_sessions = models.PositiveIntegerField(default=0)
    total_messages = models.PositiveIntegerField(default=0)
    unique_users = models.PositiveIntegerField(default=0)
    anonymous_users = models.PositiveIntegerField(default=0)
    
    # Search metrics
    total_searches = models.PositiveIntegerField(default=0)
    local_searches = models.PositiveIntegerField(default=0)
    external_searches = models.PositiveIntegerField(default=0)
    successful_searches = models.PositiveIntegerField(default=0)
    
    # Performance metrics
    average_response_time = models.FloatField(default=0.0)
    average_session_duration = models.FloatField(default=0.0)
    
    # Feedback metrics
    positive_feedback = models.PositiveIntegerField(default=0)
    negative_feedback = models.PositiveIntegerField(default=0)
    average_rating = models.FloatField(default=0.0)
    
    # Popular categories/topics
    top_search_categories = models.JSONField(default=list, blank=True)
    top_search_terms = models.JSONField(default=list, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"Analytics for {self.date}"


class BotConfiguration(models.Model):
    """Configuration settings for the chatbot"""
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField()
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Bot Configuration"
        verbose_name_plural = "Bot Configurations"
    
    def __str__(self):
        return f"{self.key}: {str(self.value)[:50]}"
    
    @classmethod
    def get_config(cls, key, default=None):
        try:
            config = cls.objects.get(key=key, is_active=True)
            return config.value
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_config(cls, key, value, description=None):
        config, created = cls.objects.get_or_create(
            key=key,
            defaults={
                'value': value,
                'description': description,
                'is_active': True
            }
        )
        if not created:
            config.value = value
            config.description = description
            config.save()
        return config