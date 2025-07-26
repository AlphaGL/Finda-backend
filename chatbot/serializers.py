# serializers.py - Enhanced serializer
from rest_framework import serializers
from .models import ChatMessage, UserVoiceSettings

class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = [
            'id', 'user_input', 'bot_response', 'timestamp',
            'is_voice_message', 'is_image_message', 'audio_file',
            'image_file', 'transcript', 'image_analysis', 'voice_response_url'
        ]

class VoiceSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserVoiceSettings
        fields = ['preferred_language', 'voice_speed', 'voice_enabled']

