# models.py - Enhanced with image and voice support
from django.conf import settings
from django.db import models
import uuid

class ChatMessage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_messages"
    )
    user_input = models.TextField()
    bot_response = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # New fields for multimedia support
    is_voice_message = models.BooleanField(default=False)
    is_image_message = models.BooleanField(default=False)
    audio_file = models.FileField(upload_to='voice_messages/', null=True, blank=True)
    image_file = models.ImageField(upload_to='image_searches/', null=True, blank=True)
    transcript = models.TextField(blank=True)  # For voice transcription
    image_analysis = models.TextField(blank=True)  # For image analysis results
    voice_response_url = models.URLField(blank=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        msg_type = ""
        if self.is_voice_message:
            msg_type = "[VOICE] "
        elif self.is_image_message:
            msg_type = "[IMAGE] "
        return f"{msg_type}{self.timestamp:%Y-%m-%d %H:%M} | {self.user.username}: {self.user_input[:30]}"

class UserVoiceSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="voice_settings"
    )
    preferred_language = models.CharField(max_length=10, default='en')
    voice_speed = models.FloatField(default=1.0)
    voice_enabled = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.username} - Voice Settings"