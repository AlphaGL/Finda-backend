# management/commands/test_integration.py
from django.core.management.base import BaseCommand
import asyncio
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Test the complete chatbot integration with SerpAPI'

    def add_arguments(self, parser):
        parser.add_argument('--query', type=str, default='iPhone 15', help='Search query to test')

    def handle(self, *args, **options):
        query = options['query']
        
        self.stdout.write(
            self.style.SUCCESS(f'🚀 Testing Complete Integration with query: "{query}"')
        )
        
        # Run the test
        asyncio.run(self.run_integration_test(query))

    async def run_integration_test(self, query):
        """Run the complete integration test"""
        try:
            context = {
                'location_context': {
                    'country': 'Nigeria',
                    'city': 'Lagos',
                    'state': 'Lagos'
                },
                'user_preferences': {},
                'conversation_history': [],
                'recent_searches': []
            }
            
            # Import and initialize the router
            from chatbot.services.smart_router import SmartChatbotRouter
            router = SmartChatbotRouter()
            
            # Run the test
            self.stdout.write(f"📋 Testing complete chatbot flow...")
            self.stdout.write(f"Query: {query}")
            self.stdout.write(f"Context: {context}")
            
            # Execute the search
            result = await router.process_message(
                message=query,
                context=context
            )
            
            # Extract and format the response - FIXED
            response = result.get('final_response', 'No response generated')
            
            # Ensure response is a string
            if isinstance(response, dict):
                response = f"Response data: {response}"
            elif not isinstance(response, str):
                response = str(response)
            
            # Handle empty or very short responses
            if not response or len(response.strip()) < 5:
                response = f"Short response received: '{response}'. Check AI generation."
            
            # Display results
            self.stdout.write(f"✅ Integration Test Complete!")
            self.stdout.write(f"Success: {result.get('success', False)}")
            self.stdout.write(f"Strategy: {result.get('search_strategy', 'unknown')}")
            
            local_results = result.get('local_results', {})
            external_results = result.get('external_results', {})
            
            self.stdout.write(f"Local Results: {local_results.get('total_results', 0)}")
            self.stdout.write(f"External Results: {external_results.get('total_found', 0)}")
            self.stdout.write(f"🤖 AI Response ({len(response)} chars):")
            
            # Display response with proper string handling
            display_response = response[:500] + "..." if len(response) > 500 else response
            self.stdout.write(display_response)
            
            # Show some debug info if results are empty
            if result.get('success') and (local_results.get('total_results', 0) == 0 and external_results.get('total_found', 0) == 0):
                self.stdout.write("⚠️ No results found. This might indicate:")
                self.stdout.write("  - Database is empty")
                self.stdout.write("  - Search filters are too restrictive")
                self.stdout.write("  - External search API is not configured")
                self.stdout.write("  - Query intent detection needs improvement")
            
        except Exception as e:
            self.stdout.write(f"❌ Integration test failed: {str(e)}")
            import traceback
            self.stdout.write("Full traceback:")
            traceback.print_exc()