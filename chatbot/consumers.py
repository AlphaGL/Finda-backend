# ai_chatbot/consumers.py - COMPLETED
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError

from .models import ChatSession, ChatMessage
from .services.smart_router import SmartChatbotRouter
from .utils.session_manager import ChatSessionManager
from .serializers import ChatMessageRequestSerializer

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time chat functionality
    Handles live chat sessions with typing indicators and instant responses
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chat_session = None
        self.session_manager = ChatSessionManager()
        self.router = SmartChatbotRouter()
        self.user = None
        self.session_id = None
        self.room_group_name = None
        
    async def connect(self):
        """Handle WebSocket connection"""
        try:
            # Extract session ID from URL or create new one
            self.session_id = self.scope['url_route']['kwargs'].get('session_id')
            
            if not self.session_id:
                self.session_id = self.session_manager.generate_session_id()
            
            # Set room group name
            self.room_group_name = f"chat_{self.session_id}"
            
            # Get or create chat session
            self.user = self.scope.get('user', AnonymousUser())
            
            # Get or create session
            self.chat_session = await self._get_or_create_session()
            
            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            # Accept the connection
            await self.accept()
            
            # Send connection confirmation
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'session_id': str(self.chat_session.id),
                'message': 'Connected successfully',
                'timestamp': datetime.now().isoformat()
            }))
            
            logger.info(f"WebSocket connected: session {self.session_id}")
            
        except Exception as e:
            logger.error(f"Error connecting WebSocket: {str(e)}")
            await self.close(code=4000)
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            # Leave room group
            if self.room_group_name:
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )
            
            # Update session status
            if self.chat_session:
                await self._update_session_status('inactive')
            
            logger.info(f"WebSocket disconnected: session {self.session_id}, code: {close_code}")
            
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket: {str(e)}")
    
    async def receive(self, text_data):
        """Handle received WebSocket message"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'chat_message')
            
            if message_type == 'chat_message':
                await self._handle_chat_message(data)
            elif message_type == 'typing_indicator':
                await self._handle_typing_indicator(data)
            elif message_type == 'ping':
                await self._handle_ping()
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Unknown message type',
                    'timestamp': datetime.now().isoformat()
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format',
                'timestamp': datetime.now().isoformat()
            }))
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Error processing message',
                'timestamp': datetime.now().isoformat()
            }))
    
    async def _handle_chat_message(self, data):
        """Handle incoming chat message"""
        try:
            message_text = data.get('message', '').strip()
            message_type = data.get('message_type', 'text')
            
            if not message_text:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Message cannot be empty',
                    'timestamp': datetime.now().isoformat()
                }))
                return
            
            # Save user message
            user_message = await self._save_user_message(message_text, message_type)
            
            # Send typing indicator
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_status',
                    'typing': True,
                    'sender': 'bot'
                }
            )
            
            # Build context
            context = await self._build_context()
            
            # Process message with router
            processing_result = await self.router.process_message(
                message_text, message_type, None, context
            )
            
            # Save bot response
            bot_message = await self._save_bot_response(processing_result, user_message)
            
            # Stop typing indicator
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_status',
                    'typing': False,
                    'sender': 'bot'
                }
            )
            
            # Send response
            await self.send(text_data=json.dumps({
                'type': 'chat_response',
                'message_id': str(bot_message.id),
                'response': processing_result.get('final_response', ''),
                'search_results': {
                    'local': processing_result.get('local_results', {}),
                    'external': processing_result.get('external_results', {})
                },
                'metadata': processing_result.get('metadata', {}),
                'timestamp': datetime.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error handling chat message: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to process your message',
                'timestamp': datetime.now().isoformat()
            }))
    
    async def _handle_typing_indicator(self, data):
        """Handle typing indicator"""
        typing = data.get('typing', False)
        
        # Broadcast typing status to other clients in the group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_status',
                'typing': typing,
                'sender': 'user'
            }
        )
    
    async def _handle_ping(self):
        """Handle ping/keepalive"""
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'timestamp': datetime.now().isoformat()
        }))
    
    async def typing_status(self, event):
        """Send typing status to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'typing_indicator',
            'typing': event['typing'],
            'sender': event['sender'],
            'timestamp': datetime.now().isoformat()
        }))
    
    @database_sync_to_async
    def _get_or_create_session(self):
        """Get or create chat session"""
        try:
            if self.user.is_authenticated:
                session, created = ChatSession.objects.get_or_create(
                    user=self.user,
                    session_id=self.session_id,
                    defaults={
                        'status': 'active',
                        'ip_address': self._get_client_ip(),
                        'user_agent': self.scope.get('headers', {}).get(b'user-agent', b'').decode()[:500]
                    }
                )
            else:
                session, created = ChatSession.objects.get_or_create(
                    session_id=self.session_id,
                    user__isnull=True,
                    defaults={
                        'status': 'active',
                        'ip_address': self._get_client_ip(),
                        'user_agent': self.scope.get('headers', {}).get(b'user-agent', b'').decode()[:500]
                    }
                )
            
            if not created:
                session.status = 'active'
                session.last_activity = datetime.now()
                session.save()
            
            return session
            
        except Exception as e:
            logger.error(f"Error getting/creating session: {str(e)}")
            raise
    
    @database_sync_to_async
    def _save_user_message(self, message_text, message_type):
        """Save user message to database"""
        return ChatMessage.objects.create(
            chat_session=self.chat_session,
            sender_type='user',
            message_type=message_type,
            content=message_text,
            context_data={}
        )
    
    @database_sync_to_async
    def _save_bot_response(self, processing_result, user_message):
        """Save bot response to database"""
        return ChatMessage.objects.create(
            chat_session=self.chat_session,
            sender_type='bot',
            message_type='text',
            content=processing_result.get('final_response', ''),
            search_mode=processing_result.get('search_strategy', 'unknown'),
            response_time=processing_result.get('metadata', {}).get('processing_time', 0),
            confidence_score=processing_result.get('metadata', {}).get('confidence_score', 0),
            search_results_count=(
                processing_result.get('local_results', {}).get('total_results', 0) +
                processing_result.get('external_results', {}).get('total_found', 0)
            ),
            context_data={
                'intent': processing_result.get('intent', {}),
                'search_strategy': processing_result.get('search_strategy'),
                'services_used': processing_result.get('metadata', {}).get('services_used', [])
            }
        )
    
    @database_sync_to_async
    def _build_context(self):
        """Build conversation context"""
        # Get recent messages
        recent_messages = list(self.chat_session.messages.filter(
            is_active=True
        ).order_by('-created_at')[:10])
        
        return {
            'session_id': str(self.chat_session.id),
            'user_preferences': self.chat_session.user_preferences,
            'location_context': self.chat_session.location_context,
            'conversation_history': [
                {
                    'sender_type': msg.sender_type,
                    'content': msg.content,
                    'timestamp': msg.created_at.isoformat()
                }
                for msg in reversed(recent_messages)
            ],
            'recent_searches': []
        }
    
    @database_sync_to_async
    def _update_session_status(self, status):
        """Update session status"""
        if self.chat_session:
            self.chat_session.status = status
            self.chat_session.save()
    
    def _get_client_ip(self):
        """Get client IP address"""
        headers = dict(self.scope.get('headers', []))
        
        # Check for forwarded IP
        x_forwarded_for = headers.get(b'x-forwarded-for')
        if x_forwarded_for:
            return x_forwarded_for.decode().split(',')[0].strip()
        
        # Check for real IP
        x_real_ip = headers.get(b'x-real-ip')
        if x_real_ip:
            return x_real_ip.decode()
        
        # Fallback to client address
        return self.scope.get('client', ['Unknown', None])[0]