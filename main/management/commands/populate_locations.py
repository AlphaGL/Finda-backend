# management/commands/populate_locations.py
from django.core.management.base import BaseCommand
from django.db import transaction
import json
import requests
from myapp.models import Country, State, City
import time

class Command(BaseCommand):
    help = 'Populate countries, states, and cities from REST Countries API and other sources'

    def add_arguments(self, parser):
        parser.add_argument(
            '--countries-only',
            action='store_true',
            help='Only populate countries',
        )
        parser.add_argument(
            '--specific-country',
            type=str,
            help='Populate states/cities for specific country code (e.g., NG, US)',
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing records',
        )

    def handle(self, *args, **options):
        if options['countries_only']:
            self.populate_countries(options['update_existing'])
        elif options['specific_country']:
            self.populate_country_states_cities(options['specific_country'])
        else:
            self.populate_all_locations(options['update_existing'])

    def populate_countries(self, update_existing=False):
        """Populate countries from REST Countries API"""
        self.stdout.write('Fetching countries from REST Countries API...')
        
        try:
            response = requests.get('https://restcountries.com/v3.1/all')
            response.raise_for_status()
            countries_data = response.json()
            
            with transaction.atomic():
                for country_info in countries_data:
                    country_name = country_info.get('name', {}).get('common', '')
                    country_code = country_info.get('cca2', '')  # 2-letter ISO code
                    
                    if not country_name or not country_code:
                        continue
                    
                    # Get additional info
                    phone_codes = country_info.get('idd', {})
                    phone_code = None
                    if phone_codes.get('root') and phone_codes.get('suffixes'):
                        phone_code = phone_codes['root'] + phone_codes['suffixes'][0]
                    
                    # Currency info
                    currencies = country_info.get('currencies', {})
                    currency_code = None
                    currency_symbol = None
                    if currencies:
                        first_currency = list(currencies.keys())[0]
                        currency_code = first_currency
                        currency_symbol = currencies[first_currency].get('symbol', '')
                    
                    # Flag emoji
                    flag_emoji = country_info.get('flag', '')
                    
                    # Continent
                    continent = country_info.get('region', '')
                    
                    # Check if country exists
                    country, created = Country.objects.get_or_create(
                        code=country_code,
                        defaults={
                            'name': country_name,
                            'phone_code': phone_code,
                            'currency_code': currency_code,
                            'currency_symbol': currency_symbol,
                            'flag_emoji': flag_emoji,
                            'continent': continent,
                            'is_active': True,
                        }
                    )
                    
                    if not created and update_existing:
                        country.name = country_name
                        country.phone_code = phone_code
                        country.currency_code = currency_code
                        country.currency_symbol = currency_symbol
                        country.flag_emoji = flag_emoji
                        country.continent = continent
                        country.save()
                        self.stdout.write(f'Updated: {country_name}')
                    elif created:
                        self.stdout.write(f'Created: {country_name}')
                    
                    time.sleep(0.1)  # Rate limiting
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully populated {Country.objects.count()} countries')
            )
        
        except requests.RequestException as e:
            self.stdout.write(
                self.style.ERROR(f'Error fetching countries: {e}')
            )

    def populate_country_states_cities(self, country_code):
        """Populate states and cities for a specific country"""
        try:
            country = Country.objects.get(code=country_code.upper())
        except Country.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Country with code {country_code} does not exist')
            )
            return

        self.stdout.write(f'Populating states and cities for {country.name}...')
        
        # Use different APIs based on country
        if country_code.upper() == 'US':
            self._populate_us_data(country)
        elif country_code.upper() == 'NG':
            self._populate_nigeria_data(country)
        elif country_code.upper() == 'GB':
            self._populate_uk_data(country)
        elif country_code.upper() == 'CA':
            self._populate_canada_data(country)
        else:
            self._populate_generic_country_data(country)

    def _populate_us_data(self, country):
        """Populate US states and major cities"""
        us_states = [
            ('AL', 'Alabama'), ('AK', 'Alaska'), ('AZ', 'Arizona'), ('AR', 'Arkansas'),
            ('CA', 'California'), ('CO', 'Colorado'), ('CT', 'Connecticut'), ('DE', 'Delaware'),
            ('FL', 'Florida'), ('GA', 'Georgia'), ('HI', 'Hawaii'), ('ID', 'Idaho'),
            ('IL', 'Illinois'), ('IN', 'Indiana'), ('IA', 'Iowa'), ('KS', 'Kansas'),
            ('KY', 'Kentucky'), ('LA', 'Louisiana'), ('ME', 'Maine'), ('MD', 'Maryland'),
            ('MA', 'Massachusetts'), ('MI', 'Michigan'), ('MN', 'Minnesota'), ('MS', 'Mississippi'),
            ('MO', 'Missouri'), ('MT', 'Montana'), ('NE', 'Nebraska'), ('NV', 'Nevada'),
            ('NH', 'New Hampshire'), ('NJ', 'New Jersey'), ('NM', 'New Mexico'), ('NY', 'New York'),
            ('NC', 'North Carolina'), ('ND', 'North Dakota'), ('OH', 'Ohio'), ('OK', 'Oklahoma'),
            ('OR', 'Oregon'), ('PA', 'Pennsylvania'), ('RI', 'Rhode Island'), ('SC', 'South Carolina'),
            ('SD', 'South Dakota'), ('TN', 'Tennessee'), ('TX', 'Texas'), ('UT', 'Utah'),
            ('VT', 'Vermont'), ('VA', 'Virginia'), ('WA', 'Washington'), ('WV', 'West Virginia'),
            ('WI', 'Wisconsin'), ('WY', 'Wyoming'), ('DC', 'District of Columbia')
        ]
        
        major_cities = {
            'CA': ['Los Angeles', 'San Francisco', 'San Diego', 'Sacramento', 'San Jose'],
            'NY': ['New York City', 'Buffalo', 'Rochester', 'Syracuse', 'Albany'],
            'TX': ['Houston', 'Dallas', 'Austin', 'San Antonio', 'Fort Worth'],
            'FL': ['Miami', 'Orlando', 'Tampa', 'Jacksonville', 'Tallahassee'],
            'IL': ['Chicago', 'Aurora', 'Rockford', 'Joliet', 'Springfield'],
            # Add more as needed
        }
        
        with transaction.atomic():
            for code, name in us_states:
                state, created = State.objects.get_or_create(
                    name=name,
                    country=country,
                    defaults={
                        'code': code,
                        'type': 'state' if code != 'DC' else 'district',
                        'is_active': True,
                    }
                )
                
                if created:
                    self.stdout.write(f'Created state: {name}')
                
                # Add major cities for this state
                if code in major_cities:
                    for city_name in major_cities[code]:
                        city, city_created = City.objects.get_or_create(
                            name=city_name,
                            state=state,
                            country=country,
                            defaults={
                                'is_major_city': True,
                                'is_capital': city_name == 'Sacramento' and code == 'CA',  # Example
                                'is_active': True,
                            }
                        )
                        
                        if city_created:
                            self.stdout.write(f'  Created city: {city_name}')

    def _populate_nigeria_data(self, country):
        """Populate Nigerian states and major cities"""
        nigeria_states = [
            ('AB', 'Abia'), ('AD', 'Adamawa'), ('AK', 'Akwa Ibom'), ('AN', 'Anambra'),
            ('BA', 'Bauchi'), ('BY', 'Bayelsa'), ('BE', 'Benue'), ('BO', 'Borno'),
            ('CR', 'Cross River'), ('DE', 'Delta'), ('EB', 'Ebonyi'), ('ED', 'Edo'),
            ('EK', 'Ekiti'), ('EN', 'Enugu'), ('GO', 'Gombe'), ('IM', 'Imo'),
            ('JI', 'Jigawa'), ('KD', 'Kaduna'), ('KN', 'Kano'), ('KT', 'Katsina'),
            ('KE', 'Kebbi'), ('KO', 'Kogi'), ('KW', 'Kwara'), ('LA', 'Lagos'),
            ('NA', 'Nasarawa'), ('NI', 'Niger'), ('OG', 'Ogun'), ('ON', 'Ondo'),
            ('OS', 'Osun'), ('OY', 'Oyo'), ('PL', 'Plateau'), ('RI', 'Rivers'),
            ('SO', 'Sokoto'), ('TA', 'Taraba'), ('YO', 'Yobe'), ('ZA', 'Zamfara'),
            ('FC', 'Federal Capital Territory')
        ]
        
        major_cities = {
            'LA': ['Lagos', 'Ikeja', 'Surulere', 'Victoria Island', 'Ikoyi'],
            'FC': ['Abuja', 'Garki', 'Wuse', 'Maitama', 'Asokoro'],
            'KN': ['Kano', 'Fagge', 'Nassarawa', 'Gwale'],
            'IM': ['Owerri', 'Orlu', 'Okigwe', 'Mbaise'],
            'AN': ['Awka', 'Onitsha', 'Nnewi', 'Ekwulobia'],
            # Add more as needed
        }
        
        with transaction.atomic():
            for code, name in nigeria_states:
                state, created = State.objects.get_or_create(
                    name=name,
                    country=country,
                    defaults={
                        'code': code,
                        'type': 'territory' if code == 'FC' else 'state',
                        'is_active': True,
                    }
                )
                
                if created:
                    self.stdout.write(f'Created state: {name}')
                
                # Add major cities
                if code in major_cities:
                    for city_name in major_cities[code]:
                        city, city_created = City.objects.get_or_create(
                            name=city_name,
                            state=state,
                            country=country,
                            defaults={
                                'is_major_city': True,
                                'is_capital': (city_name == 'Abuja' and code == 'FC') or 
                                            (city_name == 'Lagos' and code == 'LA'),
                                'is_active': True,
                            }
                        )
                        
                        if city_created:
                            self.stdout.write(f'  Created city: {city_name}')

    def _populate_generic_country_data(self, country):
        """Generic population using GeoNames API (requires registration)"""
        # This would require GeoNames API key
        # For now, we'll create some basic structure
        self.stdout.write(f'Generic data population not yet implemented for {country.name}')
        self.stdout.write('Consider using GeoNames API or country-specific data sources')

    def populate_all_locations(self, update_existing=False):
        """Populate all location data"""
        self.populate_countries(update_existing)
        
        # Populate major countries
        major_countries = ['US', 'NG', 'GB', 'CA', 'AU', 'IN', 'DE', 'FR']
        for country_code in major_countries:
            try:
                self.populate_country_states_cities(country_code)
                time.sleep(1)  # Rate limiting
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'Failed to populate {country_code}: {e}')
                )