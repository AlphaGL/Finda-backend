# admin.py - Enhanced admin interface
from django.contrib import admin
from chatbot.models import ChatMessage, UserVoiceSettings

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['user', 'timestamp', 'is_voice_message', 'is_image_message', 'user_input_preview']
    list_filter = ['timestamp', 'is_voice_message', 'is_image_message']
    search_fields = ['user__username', 'user_input', 'bot_response']
    readonly_fields = ['timestamp']
    
    def user_input_preview(self, obj):
        return obj.user_input[:50] + "..." if len(obj.user_input) > 50 else obj.user_input
    user_input_preview.short_description = "Message Preview"

@admin.register(UserVoiceSettings)
class UserVoiceSettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'preferred_language', 'voice_speed', 'voice_enabled']
    list_filter = ['preferred_language', 'voice_enabled']
    search_fields = ['user__username']