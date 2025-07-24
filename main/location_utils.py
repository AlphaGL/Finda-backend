# ================================
# LOCATION UTILITIES
# ================================

# location_utils.py
from django.core.cache import cache
from django.db.models import Q
from .models import Country, State, City
import json

class LocationUtils:
    """Utility class for location-related operations"""
    
    @staticmethod
    def get_countries_json():
        """Get all active countries as JSON for frontend"""
        cache_key = 'countries_json'
        countries = cache.get(cache_key)
        
        if not countries:
            countries = list(Country.objects.filter(is_active=True).values(
                'id', 'name', 'code', 'flag_emoji', 'phone_code'
            ).order_by('sort_order', 'name'))
            cache.set(cache_key, countries, 3600)  # Cache for 1 hour
        
        return countries
    
    @staticmethod
    def get_states_by_country(country_id):
        """Get states for a country"""
        cache_key = f'states_country_{country_id}'
        states = cache.get(cache_key)
        
        if not states:
            states = list(State.objects.filter(
                country_id=country_id, 
                is_active=True
            ).values(
                'id', 'name', 'code', 'type'
            ).order_by('sort_order', 'name'))
            cache.set(cache_key, states, 3600)
        
        return states
    
    @staticmethod
    def get_cities_by_state(state_id):
        """Get cities for a state"""
        cache_key = f'cities_state_{state_id}'
        cities = cache.get(cache_key)
        
        if not cities:
            cities = list(City.objects.filter(
                state_id=state_id, 
                is_active=True
            ).values(
                'id', 'name', 'is_major_city', 'is_capital'
            ).order_by('sort_order', 'name'))
            cache.set(cache_key, cities, 3600)
        
        return cities
    
    @staticmethod
    def search_locations(query, location_type='all'):
        """Search locations by name"""
        results = {}
        
        if location_type in ['all', 'country']:
            countries = Country.objects.filter(
                name__icontains=query,
                is_active=True
            ).values('id', 'name', 'code', 'flag_emoji')[:10]
            results['countries'] = list(countries)
        
        if location_type in ['all', 'state']:
            states = State.objects.filter(
                name__icontains=query,
                is_active=True
            ).select_related('country').values(
                'id', 'name', 'code', 'country__name', 'country__flag_emoji'
            )[:10]
            results['states'] = list(states)
        
        if location_type in ['all', 'city']:
            cities = City.objects.filter(
                name__icontains=query,
                is_active=True
            ).select_related('state', 'country').values(
                'id', 'name', 'state__name', 'country__name', 'country__flag_emoji'
            )[:10]
            results['cities'] = list(cities)
        
        return results
    
    @staticmethod
    def get_location_hierarchy(city_id=None, state_id=None, country_id=None):
        """Get complete location hierarchy"""
        if city_id:
            try:
                city = City.objects.select_related('state', 'country').get(
                    id=city_id, is_active=True
                )
                return {
                    'country': {'id': city.country.id, 'name': city.country.name, 'code': city.country.code},
                    'state': {'id': city.state.id, 'name': city.state.name, 'code': city.state.code},
                    'city': {'id': city.id, 'name': city.name}
                }
            except City.DoesNotExist:
                pass
        
        if state_id:
            try:
                state = State.objects.select_related('country').get(
                    id=state_id, is_active=True
                )
                return {
                    'country': {'id': state.country.id, 'name': state.country.name, 'code': state.country.code},
                    'state': {'id': state.id, 'name': state.name, 'code': state.code},
                    'city': None
                }
            except State.DoesNotExist:
                pass
        
        if country_id:
            try:
                country = Country.objects.get(id=country_id, is_active=True)
                return {
                    'country': {'id': country.id, 'name': country.name, 'code': country.code},
                    'state': None,
                    'city': None
                }
            except Country.DoesNotExist:
                pass
        
        return None
    
    @staticmethod
    def validate_location_hierarchy(country_id, state_id=None, city_id=None):
        """Validate that location hierarchy is correct"""
        try:
            country = Country.objects.get(id=country_id, is_active=True)
            
            if state_id:
                state = State.objects.get(
                    id=state_id, 
                    country=country, 
                    is_active=True
                )
                
                if city_id:
                    city = City.objects.get(
                        id=city_id,
                        state=state,
                        country=country,
                        is_active=True
                    )
                    return True, city
                
                return True, state
            
            return True, country
            
        except (Country.DoesNotExist, State.DoesNotExist, City.DoesNotExist):
            return False, None

