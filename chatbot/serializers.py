# ai_chatbot/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    ChatSession, ChatMessage, SearchQuery, SearchResult,
    UserFeedback, ChatAnalytics, BotConfiguration
)

User = get_user_model()


class ChatSessionSerializer(serializers.ModelSerializer):
    """Serializer for ChatSession model"""
    
    user_display = serializers.SerializerMethodField()
    messages_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatSession
        fields = [
            'id', 'session_id', 'user', 'user_display', 'title', 'status',
            'user_preferences', 'search_context', 'location_context',
            'messages_count', 'last_message', 'duration',
            'created_at', 'updated_at', 'last_activity'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_activity']
    
    def get_user_display(self, obj):
        """Get user display name"""
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
        return "Anonymous User"
    
    def get_message_info(self, obj):
        """Get basic message information"""
        return {
            'message_id': obj.chat_message.id,
            'content_preview': obj.chat_message.content[:100] + '...' if len(obj.chat_message.content) > 100 else obj.chat_message.content,
            'created_at': obj.chat_message.created_at
        }


class ChatAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for ChatAnalytics model"""
    
    usage_summary = serializers.SerializerMethodField()
    performance_summary = serializers.SerializerMethodField()
    feedback_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatAnalytics
        fields = [
            'date', 'total_sessions', 'total_messages', 'unique_users', 'anonymous_users',
            'total_searches', 'local_searches', 'external_searches', 'successful_searches',
            'average_response_time', 'average_session_duration',
            'positive_feedback', 'negative_feedback', 'average_rating',
            'top_search_categories', 'top_search_terms',
            'usage_summary', 'performance_summary', 'feedback_summary',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_usage_summary(self, obj):
        """Get usage summary"""
        return {
            'total_interactions': obj.total_sessions + obj.total_messages,
            'user_ratio': {
                'authenticated': obj.unique_users,
                'anonymous': obj.anonymous_users,
                'total': obj.unique_users + obj.anonymous_users
            },
            'search_distribution': {
                'local': obj.local_searches,
                'external': obj.external_searches,
                'total': obj.total_searches
            }
        }
    
    def get_performance_summary(self, obj):
        """Get performance summary"""
        return {
            'avg_response_time': round(obj.average_response_time, 2),
            'avg_session_duration': round(obj.average_session_duration, 2),
            'search_success_rate': round(
                (obj.successful_searches / obj.total_searches * 100) if obj.total_searches > 0 else 0, 
                1
            )
        }
    
    def get_feedback_summary(self, obj):
        """Get feedback summary"""
        total_feedback = obj.positive_feedback + obj.negative_feedback
        
        return {
            'total_feedback': total_feedback,
            'satisfaction_rate': round(
                (obj.positive_feedback / total_feedback * 100) if total_feedback > 0 else 0,
                1
            ),
            'average_rating': round(obj.average_rating, 1),
            'feedback_distribution': {
                'positive': obj.positive_feedback,
                'negative': obj.negative_feedback
            }
        }


class BotConfigurationSerializer(serializers.ModelSerializer):
    """Serializer for BotConfiguration model"""
    
    value_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = BotConfiguration
        fields = [
            'key', 'value', 'value_preview', 'description', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_value_preview(self, obj):
        """Get preview of configuration value"""
        value_str = str(obj.value)
        if len(value_str) > 100:
            return value_str[:100] + '...'
        return value_str


# Request/Response serializers for API endpoints
class ChatMessageRequestSerializer(serializers.Serializer):
    """Serializer for chat message requests"""
    
    message = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    message_type = serializers.ChoiceField(
        choices=['text', 'image', 'voice', 'file'],
        default='text'
    )
    session_id = serializers.UUIDField(required=False, allow_null=True)
    file = serializers.FileField(required=False, allow_null=True)
    language = serializers.CharField(max_length=5, default='en')
    enable_tts = serializers.BooleanField(default=False)
    user_location = serializers.JSONField(required=False, allow_null=True)
    
    def validate(self, data):
        """Validate chat message request"""
        message_type = data.get('message_type', 'text')
        message = data.get('message', '')
        file = data.get('file')
        
        # For text messages, content is required
        if message_type == 'text' and not message:
            raise serializers.ValidationError("Message content is required for text messages")
        
        # For file messages, file is required
        if message_type in ['image', 'voice', 'file'] and not file:
            raise serializers.ValidationError(f"File is required for {message_type} messages")
        
        # Validate file types
        if file:
            if message_type == 'image':
                allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
                if file.content_type not in allowed_types:
                    raise serializers.ValidationError("Invalid image file type")
            elif message_type == 'voice':
                allowed_types = ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/webm', 'audio/mp4']
                if file.content_type not in allowed_types:
                    raise serializers.ValidationError("Invalid audio file type")
        
        return data


class ChatMessageResponseSerializer(serializers.Serializer):
    """Serializer for chat message responses"""
    
    success = serializers.BooleanField()
    message_id = serializers.UUIDField(required=False)
    session_id = serializers.UUIDField(required=False)
    response = serializers.CharField()
    message_type = serializers.CharField()
    
    metadata = serializers.DictField(child=serializers.JSONField(), required=False)
    search_results = serializers.DictField(child=serializers.JSONField(), required=False)
    suggested_actions = serializers.ListField(
        child=serializers.DictField(),
        required=False
    )
    tts_audio = serializers.DictField(required=False)
    error = serializers.CharField(required=False)
    timestamp = serializers.DateTimeField()


class FeedbackRequestSerializer(serializers.Serializer):
    """Serializer for feedback requests"""
    
    message_id = serializers.UUIDField()
    feedback_type = serializers.ChoiceField(
        choices=['thumbs_up', 'thumbs_down', 'rating', 'comment']
    )
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    comment = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    accuracy_rating = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    helpfulness_rating = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    speed_rating = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    
    def validate(self, data):
        """Validate feedback request"""
        feedback_type = data.get('feedback_type')
        
        # Rating is required for rating feedback type
        if feedback_type == 'rating' and not data.get('rating'):
            raise serializers.ValidationError("Rating is required for rating feedback")
        
        # Comment is required for comment feedback type
        if feedback_type == 'comment' and not data.get('comment'):
            raise serializers.ValidationError("Comment is required for comment feedback")
        
        return data


class QuickSearchRequestSerializer(serializers.Serializer):
    """Serializer for quick search requests"""
    
    query = serializers.CharField(max_length=200)
    category = serializers.CharField(max_length=100, required=False, allow_blank=True)
    location = serializers.JSONField(required=False, allow_null=True)
    price_range = serializers.JSONField(required=False, allow_null=True)
    search_type = serializers.ChoiceField(
        choices=['product', 'service', 'both'],
        default='both'
    )


class QuickSearchResponseSerializer(serializers.Serializer):
    """Serializer for quick search responses"""
    
    success = serializers.BooleanField()
    query = serializers.CharField()
    results = serializers.DictField()
    search_time = serializers.FloatField()
    error = serializers.CharField(required=False)


# Utility serializers
class ProductSummarySerializer(serializers.Serializer):
    """Serializer for product summary in search results"""
    
    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()
    price = serializers.DecimalField(max_digits=15, decimal_places=2)
    formatted_price = serializers.CharField()
    currency = serializers.CharField()
    image = serializers.URLField(allow_null=True)
    condition = serializers.CharField()
    brand = serializers.CharField(allow_null=True)
    location = serializers.DictField()
    category = serializers.DictField()
    seller = serializers.DictField()
    rating = serializers.DictField()
    stats = serializers.DictField()
    features = serializers.DictField()
    url = serializers.CharField()
    type = serializers.CharField()


class ServiceSummarySerializer(serializers.Serializer):
    """Serializer for service summary in search results"""
    
    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()
    price_range = serializers.CharField()
    price_type = serializers.CharField()
    currency = serializers.CharField()
    image = serializers.URLField(allow_null=True)
    location = serializers.DictField()
    category = serializers.DictField()
    provider = serializers.DictField()
    rating = serializers.DictField()
    stats = serializers.DictField()
    features = serializers.DictField()
    url = serializers.CharField()
    type = serializers.CharField()


class ExternalProductSerializer(serializers.Serializer):
    """Serializer for external product results"""
    
    title = serializers.CharField()
    url = serializers.URLField()
    description = serializers.CharField(allow_blank=True)
    price = serializers.CharField(allow_null=True)
    image_url = serializers.URLField(allow_null=True)
    source = serializers.CharField()
    confidence = serializers.FloatField()
    link_verified = serializers.BooleanField(required=False)


# Error serializers
class ErrorResponseSerializer(serializers.Serializer):
    """Serializer for error responses"""
    
    success = serializers.BooleanField(default=False)
    error = serializers.CharField()
    error_code = serializers.CharField(required=False)
    details = serializers.DictField(required=False)
    timestamp = serializers.DateTimeField()


# Validation utilities
def validate_file_size(file, max_size_mb=10):
    """Validate file size"""
    if file.size > max_size_mb * 1024 * 1024:
        raise serializers.ValidationError(f"File size cannot exceed {max_size_mb}MB")


def validate_image_file(file):
    """Validate image file"""
    validate_file_size(file)
    
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp']
    if file.content_type not in allowed_types:
        raise serializers.ValidationError("Invalid image file type")


def validate_audio_file(file):
    """Validate audio file"""
    validate_file_size(file, max_size_mb=25)  # Larger limit for audio
    
    allowed_types = [
        'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/ogg', 
        'audio/webm', 'audio/mp4', 'audio/m4a', 'audio/flac'
    ]
    if file.content_type not in allowed_types:
        raise serializers.ValidationError("Invalid audio file type")


def user_display(self, obj):
    """Get user display name"""
    if obj.user:
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
    return f"Anonymous ({obj.session_id[:8]})"


def get_messages_count(self, obj):
    """Get total messages count"""
    return obj.messages.filter(is_active=True).count()


def get_last_message(self, obj):
    """Get last message preview"""
    last_message = obj.messages.filter(is_active=True).order_by('-created_at').first()
    if last_message:
        content = last_message.content
        return {
            'content': content[:100] + '...' if len(content) > 100 else content,
            'sender_type': last_message.sender_type,
            'created_at': last_message.created_at,
            'message_type': last_message.message_type
        }
    return None


def get_duration(self, obj):
    """Get session duration in minutes"""
    if obj.created_at and obj.last_activity:
        duration = obj.last_activity - obj.created_at
        return duration.total_seconds() / 60  # Return minutes
    return 0

class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for ChatMessage model"""
    
    session_info = serializers.SerializerMethodField()
    has_search_results = serializers.SerializerMethodField()
    feedback_summary = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatMessage
        fields = [
            'id', 'chat_session', 'session_info', 'message_type', 'sender_type',
            'content', 'image', 'voice_file', 'attachment', 'attachments',
            'search_mode', 'response_time', 'confidence_score', 'search_results_count',
            'context_data', 'intent_detected', 'entities_extracted',
            'has_search_results', 'feedback_summary',
            'is_active', 'is_edited', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'response_time', 'confidence_score', 'search_results_count',
            'created_at', 'updated_at'
        ]
    
    def get_session_info(self, obj):
        """Get basic session information"""
        return {
            'session_id': obj.chat_session.session_id,
            'user_id': obj.chat_session.user_id,
            'status': obj.chat_session.status
        }
    
    def get_has_search_results(self, obj):
        """Check if message has associated search results"""
        return obj.search_queries.exists()
    
    def get_feedback_summary(self, obj):
        """Get feedback summary for bot messages"""
        if obj.sender_type != 'bot':
            return None
        
        feedbacks = obj.feedbacks.all()
        if not feedbacks.exists():
            return None
        
        positive = feedbacks.filter(feedback_type='thumbs_up').count()
        negative = feedbacks.filter(feedback_type='thumbs_down').count()
        ratings = feedbacks.filter(rating__isnull=False)
        avg_rating = ratings.aggregate(avg=serializers.models.Avg('rating'))['avg']
        
        return {
            'total_feedback': feedbacks.count(),
            'positive': positive,
            'negative': negative,
            'average_rating': round(avg_rating, 1) if avg_rating else None,
            'rating_count': ratings.count()
        }
    
    def get_attachments(self, obj):
        """Get attachment information"""
        attachments = []
        
        if obj.image:
            attachments.append({
                'type': 'image',
                'url': obj.image.url,
                'filename': obj.image.public_id if hasattr(obj.image, 'public_id') else 'image'
            })
        
        if obj.voice_file:
            attachments.append({
                'type': 'voice',
                'url': obj.voice_file.url,
                'filename': obj.voice_file.public_id if hasattr(obj.voice_file, 'public_id') else 'voice'
            })
        
        if obj.attachment:
            attachments.append({
                'type': 'file',
                'url': obj.attachment.url,
                'filename': obj.attachment.public_id if hasattr(obj.attachment, 'public_id') else 'file'
            })
        
        return attachments


class SearchQuerySerializer(serializers.ModelSerializer):
    """Serializer for SearchQuery model"""
    
    message_info = serializers.SerializerMethodField()
    results_preview = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = SearchQuery
        fields = [
            'id', 'chat_message', 'message_info', 'query_text', 'search_type',
            'source_used', 'filters', 'location_context',
            'local_results_count', 'external_results_count', 'total_results_shown',
            'search_duration', 'success_rate', 'results_preview', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_message_info(self, obj):
        """Get basic message information"""
        return {
            'message_id': obj.chat_message.id,
            'sender_type': obj.chat_message.sender_type,
            'content_preview': obj.chat_message.content[:50] + '...' if len(obj.chat_message.content) > 50 else obj.chat_message.content
        }
    
    def get_results_preview(self, obj):
        """Get preview of search results"""
        results = obj.results.all()[:3]  # Top 3 results
        return [
            {
                'title': result.title,
                'result_type': result.result_type,
                'relevance_score': result.relevance_score,
                'position': result.position
            }
            for result in results
        ]
    
    def get_success_rate(self, obj):
        """Calculate success rate based on results"""
        if obj.total_results_shown == 0:
            return 0.0
        return min(1.0, obj.total_results_shown / 10)  # Normalize to 1.0 for 10+ results


class SearchResultSerializer(serializers.ModelSerializer):
    """Serializer for SearchResult model"""
    
    query_info = serializers.SerializerMethodField()
    is_local_result = serializers.SerializerMethodField()
    
    class Meta:
        model = SearchResult
        fields = [
            'id', 'search_query', 'query_info', 'result_type', 'title', 'description',
            'url', 'image_url', 'content_type', 'object_id', 'external_data',
            'price_info', 'location_info', 'relevance_score', 'position',
            'click_count', 'was_clicked', 'is_local_result', 'created_at'
        ]
        read_only_fields = ['id', 'click_count', 'was_clicked', 'created_at']
    
    def get_query_info(self, obj):
        """Get basic query information"""
        return {
            'query_text': obj.search_query.query_text,
            'search_type': obj.search_query.search_type,
            'source_used': obj.search_query.source_used
        }
    
    def get_is_local_result(self, obj):
        """Check if this is a local database result"""
        return obj.result_type in ['product', 'service']


class UserFeedbackSerializer(serializers.ModelSerializer):
    """Serializer for UserFeedback model"""
    
    user_display = serializers.SerializerMethodField()
    message_info = serializers.SerializerMethodField()
    
    class Meta:
        model = UserFeedback
        fields = [
            'id', 'chat_message', 'message_info', 'user', 'user_display',
            'feedback_type', 'rating', 'comment',
            'accuracy_rating', 'helpfulness_rating', 'speed_rating',
            'ip_address', 'created_at'
        ]
        read_only_fields = ['id', 'ip_address', 'created_at']
    def get_user_display(self, obj):
        """Get user display name"""
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
        return f"Anonymous ({obj.session_id[:8]})"