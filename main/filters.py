# filters.py - Enhanced Filters with Professional Location System
import django_filters
from django.db.models import Q
from .models import Country, State, City, Category, Products, Services, ProductRating, ServiceRating


class CountryFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    code = django_filters.CharFilter(lookup_expr='iexact')
    continent = django_filters.CharFilter(lookup_expr='icontains')
    is_active = django_filters.BooleanFilter()
    
    class Meta:
        model = Country
        fields = ['name', 'code', 'continent', 'is_active']


class StateFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    country = django_filters.ModelChoiceFilter(queryset=Country.objects.filter(is_active=True))
    country_code = django_filters.CharFilter(field_name='country__code', lookup_expr='iexact')
    type = django_filters.ChoiceFilter(choices=State._meta.get_field('type').choices)
    is_active = django_filters.BooleanFilter()
    
    class Meta:
        model = State
        fields = ['name', 'country', 'country_code', 'type', 'is_active']


class CityFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    state = django_filters.ModelChoiceFilter(queryset=State.objects.filter(is_active=True))
    country = django_filters.ModelChoiceFilter(queryset=Country.objects.filter(is_active=True))
    state_code = django_filters.CharFilter(field_name='state__code', lookup_expr='iexact')
    country_code = django_filters.CharFilter(field_name='country__code', lookup_expr='iexact')
    is_capital = django_filters.BooleanFilter()
    is_major_city = django_filters.BooleanFilter()
    is_active = django_filters.BooleanFilter()
    
    class Meta:
        model = City
        fields = ['name', 'state', 'country', 'state_code', 'country_code', 
                 'is_capital', 'is_major_city', 'is_active']


class CategoryFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    category_type = django_filters.ChoiceFilter(choices=Category._meta.get_field('category_type').choices)
    parent = django_filters.ModelChoiceFilter(queryset=Category.objects.filter(is_active=True))
    is_featured = django_filters.BooleanFilter()
    is_active = django_filters.BooleanFilter()
    
    class Meta:
        model = Category
        fields = ['name', 'category_type', 'parent', 'is_featured', 'is_active']


class ProductsFilter(django_filters.FilterSet):
    # Basic filters
    product_name = django_filters.CharFilter(lookup_expr='icontains')
    product_brand = django_filters.CharFilter(lookup_expr='icontains')
    product_condition = django_filters.ChoiceFilter(choices=Products._meta.get_field('product_condition').choices)
    product_status = django_filters.ChoiceFilter(choices=Products._meta.get_field('product_status').choices)
    
    # Price filters
    min_price = django_filters.NumberFilter(field_name='product_price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='product_price', lookup_expr='lte')
    price_range = django_filters.RangeFilter(field_name='product_price')
    is_negotiable = django_filters.BooleanFilter()
    
    # Location filters
    country = django_filters.ModelChoiceFilter(queryset=Country.objects.filter(is_active=True))
    state = django_filters.ModelChoiceFilter(queryset=State.objects.filter(is_active=True))
    city = django_filters.ModelChoiceFilter(queryset=City.objects.filter(is_active=True))
    country_code = django_filters.CharFilter(field_name='country__code', lookup_expr='iexact')
    state_name = django_filters.CharFilter(field_name='state__name', lookup_expr='icontains')
    city_name = django_filters.CharFilter(field_name='city__name', lookup_expr='icontains')
    
    # Category filters
    category = django_filters.ModelChoiceFilter(queryset=Category.objects.filter(is_active=True))
    category_type = django_filters.CharFilter(field_name='category__category_type')
    parent_category = django_filters.CharFilter(field_name='category__parent__name', lookup_expr='icontains')
    
    # Business filters
    is_promoted = django_filters.BooleanFilter()
    is_featured = django_filters.BooleanFilter()
    is_paid = django_filters.BooleanFilter()
    
    # User filter
    user = django_filters.CharFilter(field_name='user__username', lookup_expr='icontains')
    
    # Date filters
    created_after = django_filters.DateFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateFilter(field_name='created_at', lookup_expr='lte')
    
    # Tags filter
    tags = django_filters.CharFilter(method='filter_tags')
    
    # Search filter (multiple fields)
    search = django_filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Products
        fields = [
            'product_name', 'product_brand', 'product_condition', 'product_status',
            'min_price', 'max_price', 'is_negotiable',
            'country', 'state', 'city', 'country_code', 'state_name', 'city_name',
            'category', 'category_type', 'parent_category',
            'is_promoted', 'is_featured', 'is_paid',
            'user', 'created_after', 'created_before', 'tags', 'search'
        ]
    
    def filter_tags(self, queryset, name, value):
        """Filter products by tags"""
        return queryset.filter(tags__icontains=value)
    
    def filter_search(self, queryset, name, value):
        """Search across multiple fields"""
        return queryset.filter(
            Q(product_name__icontains=value) |
            Q(product_description__icontains=value) |
            Q(product_brand__icontains=value) |
            Q(tags__icontains=value) |
            Q(category__name__icontains=value)
        )


class ServicesFilter(django_filters.FilterSet):
    # Basic filters
    service_name = django_filters.CharFilter(lookup_expr='icontains')
    provider_name = django_filters.CharFilter(lookup_expr='icontains')
    service_status = django_filters.ChoiceFilter(choices=Services._meta.get_field('service_status').choices)
    provider_experience = django_filters.ChoiceFilter(choices=Services._meta.get_field('provider_experience').choices)
    
    # Price filters
    min_price = django_filters.NumberFilter(field_name='starting_price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='max_price', lookup_expr='lte')
    price_type = django_filters.ChoiceFilter(choices=Services._meta.get_field('price_type').choices)
    
    # Location filters
    country = django_filters.ModelChoiceFilter(queryset=Country.objects.filter(is_active=True))
    state = django_filters.ModelChoiceFilter(queryset=State.objects.filter(is_active=True))
    city = django_filters.ModelChoiceFilter(queryset=City.objects.filter(is_active=True))
    country_code = django_filters.CharFilter(field_name='country__code', lookup_expr='iexact')
    state_name = django_filters.CharFilter(field_name='state__name', lookup_expr='icontains')
    city_name = django_filters.CharFilter(field_name='city__name', lookup_expr='icontains')
    serves_remote = django_filters.BooleanFilter()
    
    # Category filters
    category = django_filters.ModelChoiceFilter(queryset=Category.objects.filter(is_active=True))
    category_type = django_filters.CharFilter(field_name='category__category_type')
    parent_category = django_filters.CharFilter(field_name='category__parent__name', lookup_expr='icontains')
    
    # Business filters
    is_promoted = django_filters.BooleanFilter()
    is_featured = django_filters.BooleanFilter()
    is_paid = django_filters.BooleanFilter()
    is_verified = django_filters.BooleanFilter()
    
    # User filter
    user = django_filters.CharFilter(field_name='user__username', lookup_expr='icontains')
    
    # Date filters
    created_after = django_filters.DateFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateFilter(field_name='created_at', lookup_expr='lte')
    
    # Tags filter
    tags = django_filters.CharFilter(method='filter_tags')
    
    # Search filter (multiple fields)
    search = django_filters.CharFilter(method='filter_search')
    
    # Languages filter
    languages = django_filters.CharFilter(field_name='provider_languages', lookup_expr='icontains')
    
    class Meta:
        model = Services
        fields = [
            'service_name', 'provider_name', 'service_status', 'provider_experience',
            'min_price', 'max_price', 'price_type',
            'country', 'state', 'city', 'country_code', 'state_name', 'city_name', 'serves_remote',
            'category', 'category_type', 'parent_category',
            'is_promoted', 'is_featured', 'is_paid', 'is_verified',
            'user', 'created_after', 'created_before', 'tags', 'search', 'languages'
        ]
    
    def filter_tags(self, queryset, name, value):
        """Filter services by tags"""
        return queryset.filter(tags__icontains=value)
    
    def filter_search(self, queryset, name, value):
        """Search across multiple fields"""
        return queryset.filter(
            Q(service_name__icontains=value) |
            Q(service_description__icontains=value) |
            Q(provider_name__icontains=value) |
            Q(provider_expertise__icontains=value) |
            Q(tags__icontains=value) |
            Q(category__name__icontains=value)
        )


class ProductRatingFilter(django_filters.FilterSet):
    rating = django_filters.NumberFilter()
    min_rating = django_filters.NumberFilter(field_name='rating', lookup_expr='gte')
    max_rating = django_filters.NumberFilter(field_name='rating', lookup_expr='lte')
    would_recommend = django_filters.BooleanFilter()
    is_verified_purchase = django_filters.BooleanFilter()
    user = django_filters.CharFilter(field_name='user__username', lookup_expr='icontains')
    
    class Meta:
        model = ProductRating
        fields = ['rating', 'min_rating', 'max_rating', 'would_recommend', 'is_verified_purchase', 'user']


class ServiceRatingFilter(django_filters.FilterSet):
    rating = django_filters.NumberFilter()
    min_rating = django_filters.NumberFilter(field_name='rating', lookup_expr='gte')
    max_rating = django_filters.NumberFilter(field_name='rating', lookup_expr='lte')
    would_recommend = django_filters.BooleanFilter()
    would_hire_again = django_filters.BooleanFilter()
    is_verified_customer = django_filters.BooleanFilter()
    user = django_filters.CharFilter(field_name='user__username', lookup_expr='icontains')
    
    class Meta:
        model = ServiceRating
        fields = ['rating', 'min_rating', 'max_rating', 'would_recommend', 'would_hire_again', 'is_verified_customer', 'user']


# Advanced filter for location hierarchy
class LocationHierarchyFilter(django_filters.FilterSet):
    """Filter that respects location hierarchy"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Dynamic queryset updates based on selections
        if 'country' in self.data:
            country_id = self.data.get('country')
            if country_id:
                self.filters['state'].queryset = State.objects.filter(
                    country_id=country_id, is_active=True
                )
        
        if 'state' in self.data:
            state_id = self.data.get('state')
            if state_id:
                self.filters['city'].queryset = City.objects.filter(
                    state_id=state_id, is_active=True
                )


# Utility function for getting filter choices
def get_filter_choices():
    """Get choices for frontend filter dropdowns"""
    return {
        'countries': [
            {'id': c.id, 'name': c.name, 'code': c.code, 'flag': c.flag_emoji}
            for c in Country.objects.filter(is_active=True).order_by('sort_order', 'name')
        ],
        'categories': [
            {'id': c.id, 'name': c.name, 'type': c.category_type, 'parent': c.parent_id}
            for c in Category.objects.filter(is_active=True).order_by('sort_order', 'name')
        ],
        'product_conditions': [
            {'value': choice[0], 'label': choice[1]}
            for choice in Products._meta.get_field('product_condition').choices
        ],
        'service_experience_levels': [
            {'value': choice[0], 'label': choice[1]}
            for choice in Services._meta.get_field('provider_experience').choices
        ],
        'price_types': [
            {'value': choice[0], 'label': choice[1]}
            for choice in Services._meta.get_field('price_type').choices
        ]
    }