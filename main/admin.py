# admin.py - Complete Admin Configuration
from django.contrib import admin
from django.db.models import Count, Avg
from django.utils.html import format_html
from .models import (
    Country, State, City, Category, Products, Services,
    ProductRating, ServiceRating, UserFavorite, SearchHistory, LocationCache
)

# ================================
# LOCATION ADMIN CONFIGURATIONS
# ================================

@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = [
        'flag_display', 'name', 'code', 'phone_code', 
        'currency_display', 'continent', 'states_count', 
        'products_count', 'services_count', 'is_active'
    ]
    list_filter = ['continent', 'is_active', 'currency_code']
    search_fields = ['name', 'code', 'phone_code']
    ordering = ['sort_order', 'name']
    list_editable = ['is_active', 'sort_order']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'flag_emoji', 'continent')
        }),
        ('Currency & Contact', {
            'fields': ('phone_code', 'currency_code', 'currency_symbol')
        }),
        ('Settings', {
            'fields': ('is_active', 'sort_order')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            states_count=Count('states'),
            products_count=Count('products'),
            services_count=Count('services')
        )
    
    def flag_display(self, obj):
        return f"{obj.flag_emoji} {obj.name}" if obj.flag_emoji else obj.name
    flag_display.short_description = 'Country'
    flag_display.admin_order_field = 'name'
    
    def currency_display(self, obj):
        if obj.currency_code and obj.currency_symbol:
            return f"{obj.currency_code} ({obj.currency_symbol})"
        return obj.currency_code or '-'
    currency_display.short_description = 'Currency'
    
    def states_count(self, obj):
        return obj.states_count
    states_count.short_description = 'States'
    states_count.admin_order_field = 'states_count'
    
    def products_count(self, obj):
        return obj.products_count
    products_count.short_description = 'Products'
    products_count.admin_order_field = 'products_count'
    
    def services_count(self, obj):
        return obj.services_count
    services_count.short_description = 'Services'
    services_count.admin_order_field = 'services_count'


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'country_flag', 'code', 'type', 
        'cities_count', 'products_count', 'services_count', 'is_active'
    ]
    list_filter = ['country', 'type', 'is_active']
    search_fields = ['name', 'code', 'country__name']
    ordering = ['country__name', 'sort_order', 'name']
    list_editable = ['is_active', 'sort_order']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'country', 'code', 'type')
        }),
        ('Settings', {
            'fields': ('is_active', 'sort_order')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('country').annotate(
            cities_count=Count('cities'),
            products_count=Count('products'),
            services_count=Count('services')
        )
    
    def country_flag(self, obj):
        return f"{obj.country.flag_emoji} {obj.country.name}" if obj.country.flag_emoji else obj.country.name
    country_flag.short_description = 'Country'
    country_flag.admin_order_field = 'country__name'
    
    def cities_count(self, obj):
        return obj.cities_count
    cities_count.short_description = 'Cities'
    cities_count.admin_order_field = 'cities_count'
    
    def products_count(self, obj):
        return obj.products_count
    products_count.short_description = 'Products'
    products_count.admin_order_field = 'products_count'
    
    def services_count(self, obj):
        return obj.services_count
    services_count.short_description = 'Services'
    services_count.admin_order_field = 'services_count'


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'state_name', 'country_flag', 'is_capital', 
        'is_major_city', 'population_display', 'products_count', 
        'services_count', 'is_active'
    ]
    list_filter = [
        'country', 'state', 'is_capital', 'is_major_city', 'is_active'
    ]
    search_fields = ['name', 'state__name', 'country__name']
    ordering = ['country__name', 'state__name', 'sort_order', 'name']
    list_editable = ['is_active', 'is_capital', 'is_major_city']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'country', 'state')
        }),
        ('Geographic Data', {
            'fields': ('latitude', 'longitude', 'timezone', 'population')
        }),
        ('City Status', {
            'fields': ('is_capital', 'is_major_city', 'is_active', 'sort_order')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'state', 'country'
        ).annotate(
            products_count=Count('products'),
            services_count=Count('services')
        )
    
    def state_name(self, obj):
        return obj.state.name
    state_name.short_description = 'State'
    state_name.admin_order_field = 'state__name'
    
    def country_flag(self, obj):
        return f"{obj.country.flag_emoji} {obj.country.name}" if obj.country.flag_emoji else obj.country.name
    country_flag.short_description = 'Country'
    country_flag.admin_order_field = 'country__name'
    
    def population_display(self, obj):
        if obj.population:
            return f"{obj.population:,}"
        return '-'
    population_display.short_description = 'Population'
    population_display.admin_order_field = 'population'
    
    def products_count(self, obj):
        return obj.products_count
    products_count.short_description = 'Products'
    products_count.admin_order_field = 'products_count'
    
    def services_count(self, obj):
        return obj.services_count
    services_count.short_description = 'Services'
    services_count.admin_order_field = 'services_count'


# ================================
# CATEGORY ADMIN CONFIGURATION
# ================================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = [
        'icon_display', 'name', 'category_type', 'parent', 
        'subcategories_count', 'products_count', 'services_count',
        'is_featured', 'is_active'
    ]
    list_filter = ['category_type', 'parent', 'is_featured', 'is_active']
    search_fields = ['name', 'description']
    ordering = ['sort_order', 'name']
    list_editable = ['is_active', 'is_featured', 'sort_order']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'category_type')
        }),
        ('Hierarchy', {
            'fields': ('parent',)
        }),
        ('Display', {
            'fields': ('icon', 'image')
        }),
        ('Settings', {
            'fields': ('is_featured', 'is_active', 'sort_order')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            subcategories_count=Count('subcategories'),
            products_count=Count('products'),
            services_count=Count('services')
        )
    
    def icon_display(self, obj):
        if obj.icon:
            return format_html('<span style="font-size: 16px;">{}</span> {}', obj.icon, obj.name)
        return obj.name
    icon_display.short_description = 'Category'
    icon_display.admin_order_field = 'name'
    
    def subcategories_count(self, obj):
        return obj.subcategories_count
    subcategories_count.short_description = 'Subcategories'
    subcategories_count.admin_order_field = 'subcategories_count'
    
    def products_count(self, obj):
        return obj.products_count
    products_count.short_description = 'Products'
    products_count.admin_order_field = 'products_count'
    
    def services_count(self, obj):
        return obj.services_count
    services_count.short_description = 'Services'
    services_count.admin_order_field = 'services_count'


# ================================
# PRODUCTS ADMIN CONFIGURATION
# ================================

@admin.register(Products)
class ProductsAdmin(admin.ModelAdmin):
    list_display = [
        'product_name', 'user', 'category', 'price_display', 
        'location_display', 'product_status', 'product_condition',
        'rating_display', 'views_count', 'is_promoted', 'is_featured'
    ]
    list_filter = [
        'product_status', 'product_condition', 'category', 'country', 
        'state', 'is_promoted', 'is_featured', 'is_paid', 'created_at'
    ]
    search_fields = [
        'product_name', 'product_description', 'user__username', 
        'user__email', 'product_brand', 'product_model'
    ]
    ordering = ['-is_promoted', '-is_featured', '-created_at']
    list_editable = ['product_status', 'is_promoted', 'is_featured']
    prepopulated_fields = {'slug': ('product_name',)}
    readonly_fields = [
        'slug', 'views_count', 'favorites_count', 'created_at', 
        'updated_at', 'published_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'product_name', 'slug', 'product_description', 'category')
        }),
        ('Images', {
            'fields': ('featured_image', 'gallery_images')
        }),
        ('Pricing', {
            'fields': ('product_price', 'original_price', 'currency', 'is_negotiable')
        }),
        ('Location', {
            'fields': ('country', 'state', 'city', 'address_details')
        }),
        ('Product Details', {
            'fields': ('product_brand', 'product_model', 'product_condition', 'tags')
        }),
        ('Contact Information', {
            'fields': ('provider_phone', 'provider_email', 'provider_whatsapp')
        }),
        ('Status & Promotion', {
            'fields': ('product_status', 'is_paid', 'is_promoted', 'is_featured', 'promotion_fee')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('views_count', 'favorites_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'published_at', 'expires_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'category', 'country', 'state', 'city'
        ).annotate(
            avg_rating=Avg('product_ratings__rating')
        )
    
    def price_display(self, obj):
        return obj.get_formatted_price()
    price_display.short_description = 'Price'
    price_display.admin_order_field = 'product_price'
    
    def location_display(self, obj):
        return f"{obj.city.name}, {obj.state.name}"
    location_display.short_description = 'Location'
    
    def rating_display(self, obj):
        rating = obj.average_rating()
        count = obj.rating_count()
        if rating > 0:
            return f"⭐ {rating} ({count} reviews)"
        return "No ratings"
    rating_display.short_description = 'Rating'


# ================================
# SERVICES ADMIN CONFIGURATION
# ================================

@admin.register(Services)
class ServicesAdmin(admin.ModelAdmin):
    list_display = [
        'service_name', 'provider_name', 'category', 'price_range_display',
        'location_display', 'service_status', 'provider_experience',
        'rating_display', 'views_count', 'is_promoted', 'is_featured'
    ]
    list_filter = [
        'service_status', 'provider_experience', 'category', 'country',
        'state', 'is_promoted', 'is_featured', 'is_verified', 'serves_remote'
    ]
    search_fields = [
        'service_name', 'service_description', 'provider_name',
        'provider_title', 'user__username', 'user__email'
    ]
    ordering = ['-is_promoted', '-is_featured', '-created_at']
    list_editable = ['service_status', 'is_promoted', 'is_featured', 'is_verified']
    prepopulated_fields = {'slug': ('service_name',)}
    readonly_fields = [
        'slug', 'views_count', 'contacts_count', 'created_at',
        'updated_at', 'published_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'service_name', 'slug', 'service_description', 'category')
        }),
        ('Provider Information', {
            'fields': (
                'provider_name', 'provider_title', 'provider_bio',
                'provider_expertise', 'provider_experience', 'provider_certifications',
                'provider_languages'
            )
        }),
        ('Contact Information', {
            'fields': (
                'provider_email', 'provider_phone', 'provider_whatsapp',
                'provider_website', 'provider_linkedin'
            )
        }),
        ('Location & Service Area', {
            'fields': ('country', 'state', 'city', 'serves_remote', 'service_radius')
        }),
        ('Pricing', {
            'fields': ('starting_price', 'max_price', 'currency', 'price_type')
        }),
        ('Service Details', {
            'fields': ('response_time', 'availability', 'tags')
        }),
        ('Images', {
            'fields': ('featured_image', 'gallery_images')
        }),
        ('Status & Promotion', {
            'fields': (
                'service_status', 'is_paid', 'is_promoted', 'is_featured',
                'is_verified', 'promotion_fee'
            )
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('views_count', 'contacts_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'published_at', 'expires_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'category', 'country', 'state', 'city'
        ).annotate(
            avg_rating=Avg('service_ratings__rating')
        )
    
    def price_range_display(self, obj):
        return obj.get_formatted_price_range()
    price_range_display.short_description = 'Price Range'
    
    def location_display(self, obj):
        location = f"{obj.city.name}, {obj.state.name}"
        if obj.serves_remote:
            location += " (Remote)"
        return location
    location_display.short_description = 'Location'
    
    def rating_display(self, obj):
        rating = obj.average_rating()
        count = obj.rating_count()
        if rating > 0:
            return f"⭐ {rating} ({count} reviews)"
        return "No ratings"
    rating_display.short_description = 'Rating'


# ================================
# RATING ADMIN CONFIGURATIONS
# ================================

@admin.register(ProductRating)
class ProductRatingAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'user', 'rating', 'review_title',
        'would_recommend', 'is_verified_purchase', 'helpful_count', 'created_at'
    ]
    list_filter = [
        'rating', 'would_recommend', 'is_verified_purchase', 'is_active', 'created_at'
    ]
    search_fields = ['product__product_name', 'user__username', 'review_title', 'review']
    ordering = ['-created_at']
    readonly_fields = ['helpful_count', 'created_at', 'updated_at']


@admin.register(ServiceRating)
class ServiceRatingAdmin(admin.ModelAdmin):
    list_display = [
        'service', 'user', 'rating', 'review_title',
        'would_recommend', 'would_hire_again', 'is_verified_customer', 'created_at'
    ]
    list_filter = [
        'rating', 'would_recommend', 'would_hire_again', 
        'is_verified_customer', 'is_active', 'created_at'
    ]
    search_fields = ['service__service_name', 'user__username', 'review_title', 'review']
    ordering = ['-created_at']
    readonly_fields = ['helpful_count', 'created_at', 'updated_at']


# ================================
# UTILITY ADMIN CONFIGURATIONS
# ================================

@admin.register(UserFavorite)
class UserFavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'favorite_item', 'favorite_type', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'product__product_name', 'service__service_name']
    ordering = ['-created_at']
    
    def favorite_item(self, obj):
        if obj.product:
            return f"Product: {obj.product.product_name}"
        elif obj.service:
            return f"Service: {obj.service.service_name}"
        return "Unknown"
    favorite_item.short_description = 'Favorite Item'
    
    def favorite_type(self, obj):
        if obj.product:
            return "Product"
        elif obj.service:
            return "Service"
        return "Unknown"
    favorite_type.short_description = 'Type'


@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'search_term', 'user_display', 'search_type', 'location_display',
        'results_count', 'created_at'
    ]
    list_filter = ['search_type', 'country', 'state', 'created_at']
    search_fields = ['search_term', 'user__username']
    ordering = ['-created_at']
    readonly_fields = ['ip_address', 'created_at']
    
    def user_display(self, obj):
        return obj.user.username if obj.user else "Anonymous"
    user_display.short_description = 'User'
    
    def location_display(self, obj):
        location_parts = []
        if obj.city:
            location_parts.append(obj.city.name)
        if obj.state:
            location_parts.append(obj.state.name)
        if obj.country:
            location_parts.append(obj.country.name)
        return ", ".join(location_parts) if location_parts else "All Locations"
    location_display.short_description = 'Location Filter'


@admin.register(LocationCache)
class LocationCacheAdmin(admin.ModelAdmin):
    list_display = ['cache_key', 'expires_at', 'created_at']
    list_filter = ['expires_at', 'created_at']
    search_fields = ['cache_key']
    ordering = ['-created_at']
    readonly_fields = ['created_at']


# ================================
# ADMIN SITE CUSTOMIZATION
# ================================

admin.site.site_header = "Your App Admin"
admin.site.site_title = "Your App Admin Portal" 
admin.site.index_title = "Welcome to Your App Administration"