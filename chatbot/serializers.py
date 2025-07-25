# chatbot/serializers.py - Enhanced Serializers
from rest_framework import serializers
from .models import (
    ChatMessage, ChatSession, UserPreference, SearchQuery, 
    ProductSuggestion, VoiceMessage, ImageAnalysis,
    ConversationContext, FeedbackRating
)


class ChatSessionSerializer(serializers.ModelSerializer):
    message_count = serializers.ReadOnlyField()
    last_message_time = serializers.ReadOnlyField()
    
    class Meta:
        model = ChatSession
        fields = [
            'id', 'title', 'preference_data', 'last_search_query',
            'last_search_type', 'created_at', 'updated_at', 'is_active',
            'message_count', 'last_message_time'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class VoiceMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoiceMessage
        fields = [
            'original_duration_seconds', 'file_size_bytes', 'audio_format',
            'transcription_engine', 'transcription_confidence', 'language_detected',
            'processing_time_ms', 'created_at'
        ]


class ImageAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImageAnalysis
        fields = [
            'original_width', 'original_height', 'file_size_bytes', 'image_format',
            'detected_objects', 'detected_text', 'dominant_colors',
            'product_category_detected', 'brand_detected', 'product_attributes',
            'overall_confidence', 'analysis_engine', 'processing_time_ms', 'created_at'
        ]


class ChatMessageSerializer(serializers.ModelSerializer):
    voice_details = VoiceMessageSerializer(read_only=True)
    image_details = ImageAnalysisSerializer(read_only=True)
    has_multimedia = serializers.ReadOnlyField()
    
    class Meta:
        model = ChatMessage
        fields = [
            'id', 'user_input', 'bot_response', 'message_type', 'timestamp',
            'audio_file', 'image_file', 'image_analysis_data', 'preference_data',
            'search_results_data', 'external_sources_offered', 'response_time_ms',
            'user_feedback', 'voice_details', 'image_details', 'has_multimedia'
        ]
        read_only_fields = ['id', 'timestamp', 'has_multimedia']


class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = [
            'preferred_categories', 'preferred_price_range', 'preferred_locations',
            'preferred_brands', 'preferred_language', 'voice_enabled',
            'image_search_enabled', 'external_sources_preference', 'response_style',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class SearchQuerySerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchQuery
        fields = [
            'id', 'original_query', 'processed_query', 'search_type',
            'internal_results_count', 'external_sources_requested',
            'result_clicked', 'user_satisfied', 'preferences_used',
            'response_time_ms', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ProductSuggestionSerializer(serializers.ModelSerializer):
    internal_product_name = serializers.CharField(source='internal_product.product_name', read_only=True)
    
    class Meta:
        model = ProductSuggestion
        fields = [
            'id', 'internal_product', 'internal_product_name', 'external_data',
            'rank_position', 'confidence_score', 'user_clicked', 'user_rating',
            'created_at'
        ]


class FeedbackRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedbackRating
        fields = [
            'id', 'helpfulness_rating', 'accuracy_rating', 'response_speed_rating',
            'feedback_text', 'issues_reported', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate_helpfulness_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value


class ConversationContextSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationContext
        fields = [
            'current_intent', 'questions_asked', 'preferences_collected',
            'missing_preferences', 'last_search_results_internal',
            'last_search_results_external', 'external_sources_shown',
            'bounce_count', 'refinement_count', 'updated_at'
        ]


# Input serializers for API endpoints
class TextMessageInputSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=1000)
    session_id = serializers.UUIDField(required=False)


class VoiceMessageInputSerializer(serializers.Serializer):
    audio = serializers.FileField()
    session_id = serializers.UUIDField(required=False)
    
    def validate_audio(self, value):
        # Validate file size (max 10MB)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Audio file too large. Maximum size is 10MB.")
        
        # Validate file format
        allowed_formats = ['.mp3', '.wav', '.m4a', '.ogg', '.flac']
        if not any(value.name.lower().endswith(fmt) for fmt in allowed_formats):
            raise serializers.ValidationError(
                f"Unsupported audio format. Allowed formats: {', '.join(allowed_formats)}"
            )
        
        return value


class ImageMessageInputSerializer(serializers.Serializer):
    image = serializers.ImageField()
    message = serializers.CharField(max_length=500, required=False, allow_blank=True)
    session_id = serializers.UUIDField(required=False)
    
    def validate_image(self, value):
        # Validate file size (max 5MB)
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Image file too large. Maximum size is 5MB.")
        
        # Validate dimensions
        if hasattr(value, 'image'):
            width, height = value.image.size
            if width > 4000 or height > 4000:
                raise serializers.ValidationError("Image dimensions too large. Maximum 4000x4000 pixels.")
        
        return value


class ChatResponseSerializer(serializers.Serializer):
    reply = serializers.CharField()
    session_id = serializers.UUIDField()
    message_id = serializers.IntegerField()
    timestamp = serializers.DateTimeField()
    transcribed_text = serializers.CharField(required=False)
    image_analysis = serializers.DictField(required=False)
    search_query = serializers.CharField(required=False)


class PreferenceUpdateSerializer(serializers.Serializer):
    colors = serializers.ListField(child=serializers.CharField(), required=False)
    sizes = serializers.ListField(child=serializers.CharField(), required=False)
    price_range = serializers.DictField(required=False)
    brands = serializers.ListField(child=serializers.CharField(), required=False)
    locations = serializers.ListField(child=serializers.CharField(), required=False)
    categories = serializers.ListField(child=serializers.CharField(), required=False)
    condition = serializers.CharField(required=False)


class AnalyticsSerializer(serializers.Serializer):
    total_messages = serializers.IntegerField()
    total_sessions = serializers.IntegerField()
    total_voice_messages = serializers.IntegerField()
    total_image_messages = serializers.IntegerField()
    average_session_length = serializers.FloatField()
    most_searched_categories = serializers.ListField()
    user_satisfaction_score = serializers.FloatField()
    top_external_sources = serializers.ListField()


class ChatHistorySerializer(serializers.Serializer):
    messages = ChatMessageSerializer(many=True)
    session_info = ChatSessionSerializer()
    total_count = serializers.IntegerField()
    has_more = serializers.BooleanField()