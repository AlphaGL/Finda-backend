# admin.py - Comprehensive admin interface for AI Chatbot
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Avg
from django.utils import timezone
from datetime import datetime, timedelta
import json

from .models import (
    ChatSession, ChatMessage, SearchQuery, SearchResult, 
    UserFeedback, ChatAnalytics, BotConfiguration
)


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    fields = ['sender_type', 'message_type', 'content_preview', 'created_at', 'response_time']
    readonly_fields = ['content_preview', 'created_at', 'response_time']
    extra = 0
    show_change_link = True
    
    def content_preview(self, obj):
        return obj.content[:100] + "..." if len(obj.content) > 100 else obj.content
    content_preview.short_description = "Content Preview"


class SearchQueryInline(admin.TabularInline):
    model = SearchQuery
    fields = ['query_text_preview', 'search_type', 'source_used', 'total_results_shown', 'created_at']
    readonly_fields = ['query_text_preview', 'created_at']
    extra = 0
    show_change_link = True
    
    def query_text_preview(self, obj):
        return obj.query_text[:50] + "..." if len(obj.query_text) > 50 else obj.query_text
    query_text_preview.short_description = "Query Preview"


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = [
        'session_display', 'user', 'status', 'messages_count', 
        'last_activity', 'session_duration', 'created_at'
    ]
    list_filter = ['status', 'created_at', 'last_activity']
    search_fields = ['session_id', 'user__username', 'user__email', 'title']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_activity', 'session_duration_display']
    inlines = [ChatMessageInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'session_id', 'title', 'status')
        }),
        ('Context & Preferences', {
            'fields': ('user_preferences', 'search_context', 'location_context'),
            'classes': ('collapse',)
        }),
        ('Technical Information', {
            'fields': ('ip_address', 'user_agent', 'device_info'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_activity', 'session_duration_display'),
            'classes': ('collapse',)
        }),
    )
    
    def session_display(self, obj):
        if obj.user:
            return f"{obj.user.username} - {obj.title or 'Untitled'}"
        return f"Anonymous - {obj.session_id[:8]}..."
    session_display.short_description = "Session"
    
    def messages_count(self, obj):
        return obj.messages.count()
    messages_count.short_description = "Messages"
    
    def session_duration(self, obj):
        duration = obj.last_activity - obj.created_at
        return f"{duration.total_seconds() / 60:.1f} min"
    session_duration.short_description = "Duration"
    
    def session_duration_display(self, obj):
        duration = obj.last_activity - obj.created_at
        hours, remainder = divmod(duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
    session_duration_display.short_description = "Session Duration"


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = [
        'message_preview', 'chat_session', 'sender_type', 'message_type', 
        'search_mode', 'response_time', 'confidence_score', 'created_at'
    ]
    list_filter = [
        'sender_type', 'message_type', 'search_mode', 'is_active', 
        'created_at', 'intent_detected'
    ]
    search_fields = ['content', 'chat_session__session_id', 'intent_detected']
    readonly_fields = ['id', 'created_at', 'updated_at', 'media_preview']
    
    fieldsets = (
        ('Message Information', {
            'fields': ('id', 'chat_session', 'sender_type', 'message_type', 'content')
        }),
        ('Media Attachments', {
            'fields': ('image', 'voice_file', 'attachment', 'media_preview'),
            'classes': ('collapse',)
        }),
        ('Bot Response Data', {
            'fields': (
                'search_mode', 'response_time', 'confidence_score', 
                'search_results_count', 'intent_detected', 'entities_extracted'
            ),
            'classes': ('collapse',)
        }),
        ('Context & Metadata', {
            'fields': ('context_data',),
            'classes': ('collapse',)
        }),
        ('Status & Timestamps', {
            'fields': ('is_active', 'is_edited', 'created_at', 'updated_at'),
        }),
    )
    
    def message_preview(self, obj):
        content = obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
        return f"[{obj.sender_type.upper()}] {content}"
    message_preview.short_description = "Message"
    
    def media_preview(self, obj):
        html = []
        if obj.image:
            html.append(f'<img src="{obj.image.url}" style="max-width: 200px; max-height: 100px;" />')
        if obj.voice_file:
            html.append(f'<audio controls><source src="{obj.voice_file.url}"></audio>')
        if obj.attachment:
            html.append(f'<a href="{obj.attachment.url}" target="_blank">Download Attachment</a>')
        return mark_safe('<br>'.join(html)) if html else "No media attachments"
    media_preview.short_description = "Media Preview"


class SearchResultInline(admin.TabularInline):
    model = SearchResult
    fields = ['title', 'result_type', 'position', 'relevance_score', 'was_clicked']
    readonly_fields = ['title', 'result_type', 'position', 'relevance_score', 'was_clicked']
    extra = 0
    show_change_link = True


@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    list_display = [
        'query_preview', 'search_type', 'source_used', 'total_results_shown',
        'search_duration', 'success_rate', 'created_at'
    ]
    list_filter = ['search_type', 'source_used', 'created_at']
    search_fields = ['query_text', 'chat_message__content']
    readonly_fields = ['id', 'created_at']
    inlines = [SearchResultInline]
    
    fieldsets = (
        ('Query Information', {
            'fields': ('id', 'chat_message', 'query_text', 'search_type', 'source_used')
        }),
        ('Search Parameters', {
            'fields': ('filters', 'location_context'),
            'classes': ('collapse',)
        }),
        ('Results & Performance', {
            'fields': (
                'local_results_count', 'external_results_count', 'total_results_shown',
                'search_duration', 'success_rate'
            )
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    def query_preview(self, obj):
        return obj.query_text[:60] + "..." if len(obj.query_text) > 60 else obj.query_text
    query_preview.short_description = "Query"


@admin.register(SearchResult)
class SearchResultAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'result_type', 'search_query_preview', 'position', 
        'relevance_score', 'click_count', 'was_clicked'
    ]
    list_filter = ['result_type', 'was_clicked', 'created_at']
    search_fields = ['title', 'description', 'search_query__query_text']
    readonly_fields = ['id', 'created_at', 'result_preview']
    
    fieldsets = (
        ('Result Information', {
            'fields': ('id', 'search_query', 'result_type', 'title', 'description')
        }),
        ('Links & Media', {
            'fields': ('url', 'image_url', 'result_preview'),
            'classes': ('collapse',)
        }),
        ('Local Content Reference', {
            'fields': ('content_type', 'object_id', 'content_object'),
            'classes': ('collapse',)
        }),
        ('External Data', {
            'fields': ('external_data', 'price_info', 'location_info'),
            'classes': ('collapse',)
        }),
        ('Ranking & Interaction', {
            'fields': ('relevance_score', 'position', 'click_count', 'was_clicked')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    def search_query_preview(self, obj):
        return obj.search_query.query_text[:30] + "..." if len(obj.search_query.query_text) > 30 else obj.search_query.query_text
    search_query_preview.short_description = "Query"
    
    def result_preview(self, obj):
        html = []
        if obj.image_url:
            html.append(f'<img src="{obj.image_url}" style="max-width: 150px; max-height: 75px;" />')
        if obj.url:
            html.append(f'<a href="{obj.url}" target="_blank">View Result</a>')
        return mark_safe('<br>'.join(html)) if html else "No preview available"
    result_preview.short_description = "Preview"


@admin.register(UserFeedback)
class UserFeedbackAdmin(admin.ModelAdmin):
    list_display = [
        'feedback_display', 'user', 'feedback_type', 'rating', 
        'accuracy_rating', 'helpfulness_rating', 'created_at'
    ]
    list_filter = ['feedback_type', 'rating', 'created_at']
    search_fields = ['comment', 'user__username', 'chat_message__content']
    readonly_fields = ['id', 'created_at']
    
    fieldsets = (
        ('Feedback Information', {
            'fields': ('id', 'chat_message', 'user', 'feedback_type')
        }),
        ('Ratings', {
            'fields': ('rating', 'accuracy_rating', 'helpfulness_rating', 'speed_rating')
        }),
        ('Comments', {
            'fields': ('comment',)
        }),
        ('Metadata', {
            'fields': ('ip_address', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def feedback_display(self, obj):
        if obj.feedback_type == 'rating' and obj.rating:
            return f"⭐ {obj.rating}/5"
        elif obj.feedback_type == 'thumbs_up':
            return "👍 Positive"
        elif obj.feedback_type == 'thumbs_down':
            return "👎 Negative"
        else:
            return f"{obj.feedback_type}"
    feedback_display.short_description = "Feedback"


@admin.register(ChatAnalytics)
class ChatAnalyticsAdmin(admin.ModelAdmin):
    list_display = [
        'date', 'total_sessions', 'total_messages', 'unique_users',
        'total_searches', 'average_response_time', 'average_rating'
    ]
    list_filter = ['date']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Date', {
            'fields': ('date',)
        }),
        ('Usage Metrics', {
            'fields': ('total_sessions', 'total_messages', 'unique_users', 'anonymous_users')
        }),
        ('Search Metrics', {
            'fields': ('total_searches', 'local_searches', 'external_searches', 'successful_searches')
        }),
        ('Performance Metrics', {
            'fields': ('average_response_time', 'average_session_duration')
        }),
        ('Feedback Metrics', {
            'fields': ('positive_feedback', 'negative_feedback', 'average_rating')
        }),
        ('Popular Content', {
            'fields': ('top_search_categories', 'top_search_terms'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-date')


@admin.register(BotConfiguration)
class BotConfigurationAdmin(admin.ModelAdmin):
    list_display = ['key', 'value_preview', 'is_active', 'updated_at']
    list_filter = ['is_active', 'created_at', 'updated_at']
    search_fields = ['key', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Configuration', {
            'fields': ('key', 'value', 'description', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def value_preview(self, obj):
        value_str = json.dumps(obj.value) if isinstance(obj.value, (dict, list)) else str(obj.value)
        return value_str[:50] + "..." if len(value_str) > 50 else value_str
    value_preview.short_description = "Value"


# Custom admin site customization
admin.site.site_header = "AI Chatbot Administration"
admin.site.site_title = "AI Chatbot Admin"
admin.site.index_title = "Welcome to AI Chatbot Administration"