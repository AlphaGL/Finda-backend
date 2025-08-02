# management/commands/setup_finda_bot.py
from django.core.management.base import BaseCommand
from django.conf import settings
from chatbot.models import ExternalSourceCredentials, PopularSearchTerms
import os

class Command(BaseCommand):
    help = 'Setup FindA-Bot with initial configuration and data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-external-sources',
            action='store_true',
            help='Create external source credentials entries',
        )
        parser.add_argument(
            '--populate-popular-terms',
            action='store_true',
            help='Populate initial popular search terms',
        )
        parser.add_argument(
            '--check-config',
            action='store_true',
            help='Check FindA-Bot configuration',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Setting up FindA-Bot...')
        )

        if options['check_config']:
            self.check_configuration()

        if options['create_external_sources']:
            self.create_external_sources()

        if options['populate_popular_terms']:
            self.populate_popular_terms()

        self.stdout.write(
            self.style.SUCCESS('FindA-Bot setup completed!')
        )

    def check_configuration(self):
        """Check if all required configurations are set"""
        self.stdout.write('Checking configuration...')
        
        # Check Gemini API key
        gemini_key = os.getenv('GOOGLE_API_KEY')
        if gemini_key:
            self.stdout.write(
                self.style.SUCCESS('✓ Gemini API key is configured')
            )
        else:
            self.stdout.write(
                self.style.ERROR('✗ Gemini API key is missing. Set GOOGLE_API_KEY environment variable.')
            )

        # Check database connection
        try:
            from django.db import connection
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            self.stdout.write(
                self.style.SUCCESS('✓ Database connection is working')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Database connection failed: {e}')
            )

        # Check media settings for file uploads
        if hasattr(settings, 'MEDIA_ROOT') and settings.MEDIA_ROOT:
            self.stdout.write(
                self.style.SUCCESS('✓ Media settings configured')
            )
        else:
            self.stdout.write(
                self.style.WARNING('⚠ Media settings may not be properly configured')
            )

    def create_external_sources(self):
        """Create external source credential entries"""
        self.stdout.write('Creating external source entries...')
        
        sources = [
            {
                'name': 'amazon',
                'base_url': 'https://api.amazon.com/paapi5',
                'rate_limit': 100
            },
            {
                'name': 'jumia',
                'base_url': 'https://api.jumia.com.ng',
                'rate_limit': 200
            },
            {
                'name': 'konga',
                'base_url': 'https://api.konga.com',
                'rate_limit': 150
            }
        ]

        for source in sources:
            obj, created = ExternalSourceCredentials.objects.get_or_create(
                source_name=source['name'],
                defaults={
                    'base_url': source['base_url'],
                    'rate_limit_per_hour': source['rate_limit'],
                    'is_active': False  # Will be activated when API keys are added
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created {source["name"]} source entry')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠ {source["name"]} source already exists')
                )

    def populate_popular_terms(self):
        """Populate initial popular search terms"""
        self.stdout.write('Populating popular search terms...')
        
        initial_terms = [
            ('phone', 50, 85.0),
            ('laptop', 45, 90.0),
            ('shoes', 40, 80.0),
            ('dress', 35, 75.0),
            ('iphone', 30, 95.0),
            ('samsung', 28, 88.0),
            ('nike', 25, 82.0),
            ('food delivery', 22, 70.0),
            ('cleaning service', 20, 85.0),
            ('car repair', 18, 90.0),
            ('furniture', 15, 75.0),
            ('electronics', 12, 80.0),
            ('beauty products', 10, 78.0),
            ('home appliances', 8, 85.0),
        ]

        for term, count, success_rate in initial_terms:
            obj, created = PopularSearchTerms.objects.get_or_create(
                search_term=term,
                defaults={
                    'search_count': count,
                    'success_rate': success_rate
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Added popular term: {term}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠ Term already exists: {term}')
                )