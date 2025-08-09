# api/serializers.py - Updated for Enhanced Location System
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

from ..models import (
    Country, State, City, Category,
    Products, Services,
    ProductRating, ServiceRating,
    UserFavorite, SearchHistory
)

User = get_user_model()

# ===========================
#  USER SERIALIZER
# ===========================

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name']
        read_only_fields = ['id']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username


# ===========================
#  COUNTRY SERIALIZERS
# ===========================

class CountrySerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Country
        fields = [
            'id', 'name', 'code', 'phone_code', 'currency_code', 
            'currency_symbol', 'flag_emoji', 'continent', 'display_name'
        ]
    
    def get_display_name(self, obj):
        return f"{obj.flag_emoji} {obj.name}" if obj.flag_emoji else obj.name

# ===========================
#  STATE SERIALIZERS
# ===========================

class StateSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)
    display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = State
        fields = [
            'id', 'name', 'code', 'type', 'country', 'country_name', 'display_name'
        ]
    
    def get_display_name(self, obj):
        return f"{obj.name} ({obj.code})" if obj.code else obj.name

# ===========================
#  CITY SERIALIZERS
# ===========================

class CitySerializer(serializers.ModelSerializer):
    state_name = serializers.CharField(source='state.name', read_only=True)
    country_name = serializers.CharField(source='country.name', read_only=True)
    full_address = serializers.SerializerMethodField()
    
    class Meta:
        model = City
        fields = [
            'id', 'name', 'state', 'country', 'state_name', 'country_name',
            'latitude', 'longitude', 'population', 'is_capital', 
            'is_major_city', 'full_address'
        ]
    
    def get_full_address(self, obj):
        return obj.get_full_address()

# ===========================
#  CATEGORIES SERIALIZERS
# ===========================

class CategorySerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    subcategories = serializers.SerializerMethodField()
    full_path = serializers.SerializerMethodField()
    products_count = serializers.SerializerMethodField()  # Changed to SerializerMethodField
    services_count = serializers.SerializerMethodField()  # Changed to SerializerMethodField
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'category_type', 'parent',
            'parent_name', 'icon', 'image', 'image_url', 'is_featured', 'subcategories',
            'full_path', 'products_count', 'services_count'
        ]
    
    def get_image_url(self, obj):
        return obj.image.url if obj.image else None

    def get_subcategories(self, obj):
        children = obj.get_children()
        if children.exists():
            return CategorySerializer(children, many=True, context=self.context).data
        return []
    
    def get_full_path(self, obj):
        return obj.get_full_path()

    def get_products_count(self, obj):
        try:
            from ..models import Products  # Correct import path
            
            # Get all categories (current + all subcategories)
            all_categories = [obj] + list(obj.get_all_subcategories())
            
            # Count products - no product_type filter needed
            return Products.objects.filter(
                category__in=all_categories,
                product_status='published'
            ).count()
        except Exception as e:
            print(f"Error counting products for category {obj.id}: {e}")
            return 0

    def get_services_count(self, obj):
        try:
            from ..models import Services  # Import Services model
            
            # Get all categories (current + all subcategories)
            all_categories = [obj] + list(obj.get_all_subcategories())
            
            # Count services using Services model
            return Services.objects.filter(
                category__in=all_categories,
                service_status='published'  # Use service_status
            ).count()
        except Exception as e:
            print(f"Error counting services for category {obj.id}: {e}")
            return 0 

# ===========================
#  RATING SERIALIZERS
# ===========================

class ProductRatingSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    rating = serializers.DecimalField(
        max_digits=3,
        decimal_places=1,
        coerce_to_string=False
    )
    
    class Meta:
        model = ProductRating
        fields = [
            'id', 'user', 'user_details', 'user_name', 'rating', 'review_title',
            'review', 'pros', 'cons', 'would_recommend', 'is_verified_purchase',
            'helpful_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at', 'helpful_count']
    
    def validate_rating(self, value):
        # Convert to Decimal if it's a float
        if isinstance(value, float):
            value = Decimal(str(value))
        
        if not (Decimal('1.0') <= value <= Decimal('5.0')):
            raise serializers.ValidationError("Rating must be between 1.0 and 5.0")
        return value

class ServiceRatingSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    rating = serializers.DecimalField(
        max_digits=3,
        decimal_places=1,
        coerce_to_string=False
    )
    
    # Add validation for other rating fields if they exist
    communication_rating = serializers.DecimalField(
        max_digits=3,
        decimal_places=1,
        coerce_to_string=False,
        required=False,
        allow_null=True
    )
    
    quality_rating = serializers.DecimalField(
        max_digits=3,
        decimal_places=1,
        coerce_to_string=False,
        required=False,
        allow_null=True
    )
    
    timeliness_rating = serializers.DecimalField(
        max_digits=3,
        decimal_places=1,
        coerce_to_string=False,
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = ServiceRating
        fields = [
            'id', 'user', 'user_details', 'user_name', 'rating', 'review_title',
            'review', 'communication_rating', 'quality_rating', 'timeliness_rating',
            'would_recommend', 'would_hire_again', 'is_verified_customer',
            'helpful_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at', 'helpful_count']
    
    def validate_rating(self, value):
        # Convert to Decimal if it's a float
        if isinstance(value, float):
            value = Decimal(str(value))
        
        if not (Decimal('1.0') <= value <= Decimal('5.0')):
            raise serializers.ValidationError("Rating must be between 1.0 and 5.0")
        return value
    
    def validate_communication_rating(self, value):
        if value is not None:
            if isinstance(value, float):
                value = Decimal(str(value))
            if not (Decimal('1.0') <= value <= Decimal('5.0')):
                raise serializers.ValidationError("Communication rating must be between 1.0 and 5.0")
        return value
    
    def validate_quality_rating(self, value):
        if value is not None:
            if isinstance(value, float):
                value = Decimal(str(value))
            if not (Decimal('1.0') <= value <= Decimal('5.0')):
                raise serializers.ValidationError("Quality rating must be between 1.0 and 5.0")
        return value
    
    def validate_timeliness_rating(self, value):
        if value is not None:
            if isinstance(value, float):
                value = Decimal(str(value))
            if not (Decimal('1.0') <= value <= Decimal('5.0')):
                raise serializers.ValidationError("Timeliness rating must be between 1.0 and 5.0")
        return value

# ===========================
#  PRODUCT SERIALIZERS
# ===========================
class ProductsSerializer(serializers.ModelSerializer):
    # Images
    featured_image_url = serializers.SerializerMethodField()
    gallery_image_url = serializers.SerializerMethodField()

    # Computed fields
    average_rating = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    formatted_price = serializers.SerializerMethodField()
    discount_percentage = serializers.SerializerMethodField()
    currency_symbol = serializers.SerializerMethodField()
    full_location = serializers.SerializerMethodField()
    tags_list = serializers.SerializerMethodField()
    
    # Related object details
    user_details = UserSerializer(source='user', read_only=True)
    country_details = CountrySerializer(source='country', read_only=True)
    state_details = StateSerializer(source='state', read_only=True)
    city_details = CitySerializer(source='city', read_only=True)
    category_details = CategorySerializer(source='category', read_only=True)
    
    # Ratings (limited for performance)
    recent_ratings = serializers.SerializerMethodField()
    
    class Meta:
        model = Products
        fields = [
            # Basic fields
            'id', 'slug', 'product_name', 'product_description', 'featured_image', 'gallery_images',
            'featured_image_url', 'gallery_image_url', 'product_price', 'original_price', 'currency',
            'is_negotiable', 'product_brand', 'product_model', 'product_condition',
            'product_status', 'tags', 'address_details',
            
            # Contact info
            'provider_phone', 'provider_email', 'provider_whatsapp',
            
            # Business features
            'is_paid', 'is_promoted', 'is_featured', 'promotion_fee',
            'views_count', 'favorites_count',
            
            # SEO
            'meta_title', 'meta_description',
            
            # Timestamps
            'created_at', 'updated_at', 'published_at', 'expires_at',
            
            # Foreign keys
            'user', 'country', 'state', 'city', 'category',
            
            # Computed fields
            'average_rating', 'rating_count', 'formatted_price', 
            'discount_percentage', 'currency_symbol', 'full_location', 'tags_list',
            
            # Related details
            'user_details', 'country_details', 'state_details', 
            'city_details', 'category_details', 'recent_ratings'
        ]
        read_only_fields = [
            'id', 'slug', 'user', 'views_count', 'favorites_count', 
            'created_at', 'updated_at', 'published_at'
        ]
    
    def get_featured_image_url(self, obj):
        return obj.featured_image.url if obj.featured_image else None


    # UPDATED (handles both formats)
    def get_gallery_image_url(self, obj):
        if isinstance(obj.gallery_images, list):
            return [
                img['url'] if isinstance(img, dict) else img 
                for img in obj.gallery_images
            ]
        return []
    
    # def get_gallery_image_url(self, obj):
    #     # If already stored as full URLs in gallery_images field
    #     return obj.gallery_images if isinstance(obj.gallery_images, list) else []
    
    def get_average_rating(self, obj):
        return obj.average_rating()
    
    def get_rating_count(self, obj):
        return obj.rating_count()
    
    def get_formatted_price(self, obj):
        return obj.get_formatted_price()
    
    def get_discount_percentage(self, obj):
        return obj.get_discount_percentage()
    
    def get_currency_symbol(self, obj):
        return obj.get_currency_symbol()
    
    def get_full_location(self, obj):
        return obj.get_full_location()
    
    def get_tags_list(self, obj):
        return obj.get_tags_list()
    
    def get_recent_ratings(self, obj):
        recent = obj.product_ratings.filter(is_active=True)[:3]
        return ProductRatingSerializer(recent, many=True).data


class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Products
        fields = [
            'product_name', 'product_description', 'featured_image', 'gallery_images',
            'product_price', 'original_price', 'is_negotiable', 'country', 'state', 
            'city', 'address_details', 'category', 'tags', 'product_brand', 
            'product_model', 'product_condition', 'provider_phone', 'provider_email',
            'provider_whatsapp', 'is_promoted', 'meta_title', 'meta_description'
        ]
    
    def validate_product_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        if value > 999999999:
            raise serializers.ValidationError("Price is too high.")
        return value
    
    def validate_product_name(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Product name must be at least 3 characters long.")
        if len(value.strip()) > 200:
            raise serializers.ValidationError("Product name is too long.")
        return value.strip()
    
    def validate(self, data):
        # Validate original price if provided
        if data.get('original_price') and data.get('product_price'):
            if data['original_price'] <= data['product_price']:
                raise serializers.ValidationError(
                    "Original price must be higher than current price."
                )
        return data


class ProductUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Products
        fields = [
            'product_name', 'product_description', 'featured_image', 'gallery_images',
            'product_price', 'original_price', 'is_negotiable', 'address_details',
            'tags', 'product_brand', 'product_model', 'product_condition',
            'provider_phone', 'provider_email', 'provider_whatsapp',
            'meta_title', 'meta_description'
        ]


# ===========================
#  SERVICE SERIALIZERS
# ===========================

class ServicesSerializer(serializers.ModelSerializer):
    # Images
    featured_image_url = serializers.SerializerMethodField()
    gallery_image_url = serializers.SerializerMethodField()

    # Computed fields
    average_rating = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    formatted_price_range = serializers.SerializerMethodField()
    currency_symbol = serializers.SerializerMethodField()
    full_location = serializers.SerializerMethodField()
    tags_list = serializers.SerializerMethodField()
    
    # Related object details
    user_details = UserSerializer(source='user', read_only=True)
    country_details = CountrySerializer(source='country', read_only=True)
    state_details = StateSerializer(source='state', read_only=True)
    city_details = CitySerializer(source='city', read_only=True)
    category_details = CategorySerializer(source='category', read_only=True)
    
    # Recent ratings
    recent_ratings = serializers.SerializerMethodField()
    
    class Meta:
        model = Services
        fields = [
            # Basic fields
            'id', 'slug', 'service_name', 'service_description', 'featured_image',
            'gallery_images', 'featured_image_url', 'gallery_image_url', 'serves_remote', 'service_radius', 'tags',
            
            # Provider info
            'provider_name', 'provider_title', 'provider_bio', 'provider_expertise',
            'provider_experience', 'provider_certifications', 'provider_languages',
            
            # Contact info
            'provider_email', 'provider_phone', 'provider_whatsapp',
            'provider_website', 'provider_linkedin',
            
            # Pricing
            'starting_price', 'max_price', 'currency', 'price_type',
            
            # Service details
            'service_status', 'response_time', 'availability',
            
            # Business features
            'is_paid', 'is_promoted', 'is_featured', 'is_verified',
            'promotion_fee', 'views_count', 'contacts_count',
            
            # SEO
            'meta_title', 'meta_description',
            
            # Timestamps
            'created_at', 'updated_at', 'published_at', 'expires_at',
            
            # Foreign keys
            'user', 'country', 'state', 'city', 'category',
            
            # Computed fields
            'average_rating', 'rating_count', 'formatted_price_range',
            'currency_symbol', 'full_location', 'tags_list',
            
            # Related details
            'user_details', 'country_details', 'state_details',
            'city_details', 'category_details', 'recent_ratings'
        ]
        read_only_fields = [
            'id', 'slug', 'user', 'views_count', 'contacts_count',
            'created_at', 'updated_at', 'published_at'
        ]

    def get_featured_image_url(self, obj):
        return obj.featured_image.url if obj.featured_image else None

    # UPDATED (handles both formats)
    def get_gallery_image_url(self, obj):
        if isinstance(obj.gallery_images, list):
            return [
                img['url'] if isinstance(img, dict) else img 
                for img in obj.gallery_images
            ]
        return []
    
    # def get_gallery_image_url(self, obj):
    #     # If already stored as full URLs in gallery_images field
    #     return obj.gallery_images if isinstance(obj.gallery_images, list) else []
    
    def get_average_rating(self, obj):
        return obj.average_rating()
    
    def get_rating_count(self, obj):
        return obj.rating_count()
    
    def get_formatted_price_range(self, obj):
        return obj.get_formatted_price_range()
    
    def get_currency_symbol(self, obj):
        return obj.get_currency_symbol()
    
    def get_full_location(self, obj):
        return obj.get_full_location()
    
    def get_tags_list(self, obj):
        return obj.get_tags_list()
    
    def get_recent_ratings(self, obj):
        recent = obj.service_ratings.filter(is_active=True)[:3]
        return ServiceRatingSerializer(recent, many=True).data


class ServiceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Services
        fields = [
            'service_name', 'service_description', 'featured_image', 'gallery_images',
            'country', 'state', 'city', 'serves_remote', 'service_radius',
            'category', 'tags', 'provider_name', 'provider_title', 'provider_bio',
            'provider_expertise', 'provider_experience', 'provider_certifications',
            'provider_languages', 'provider_email', 'provider_phone',
            'provider_whatsapp', 'provider_website', 'provider_linkedin',
            'starting_price', 'max_price', 'price_type', 'response_time',
            'availability', 'is_promoted', 'meta_title', 'meta_description'
        ]
    
    def validate_service_name(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Service name must be at least 3 characters long.")
        if len(value.strip()) > 200:
            raise serializers.ValidationError("Service name is too long.")
        return value.strip()
    
    def validate_provider_email(self, value):
        if '@' not in value:
            raise serializers.ValidationError("Enter a valid email address.")
        return value.lower()
    
    def validate(self, data):
        # Validate price range
        starting_price = data.get('starting_price')
        max_price = data.get('max_price')
        
        if starting_price and max_price:
            if starting_price >= max_price:
                raise serializers.ValidationError(
                    "Starting price must be less than maximum price."
                )
        
        return data


class ServiceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Services
        fields = [
            'service_name', 'service_description', 'featured_image', 'gallery_images',
            'serves_remote', 'service_radius', 'tags', 'provider_name',
            'provider_title', 'provider_bio', 'provider_expertise',
            'provider_experience', 'provider_certifications', 'provider_languages',
            'provider_email', 'provider_phone', 'provider_whatsapp',
            'provider_website', 'provider_linkedin', 'starting_price',
            'max_price', 'price_type', 'response_time', 'availability',
            'meta_title', 'meta_description'
        ]


# ===========================
#  UTILITY SERIALIZERS
# ===========================

class UserFavoriteSerializer(serializers.ModelSerializer):
    product_details = ProductsSerializer(source='product', read_only=True)
    service_details = ServicesSerializer(source='service', read_only=True)
    item_type = serializers.SerializerMethodField()
    
    class Meta:
        model = UserFavorite
        fields = ['id', 'product', 'service', 'product_details', 'service_details', 
                 'item_type', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_item_type(self, obj):
        if obj.product:
            return 'product'
        elif obj.service:
            return 'service'
        return None


class LocationHierarchySerializer(serializers.Serializer):
    country = CountrySerializer(read_only=True)
    state = StateSerializer(read_only=True)
    city = CitySerializer(read_only=True)


# ===========================
#  PAGE SERIALIZERS
# ===========================

class HomePageSerializer(serializers.Serializer):
    promoted_products = ProductsSerializer(many=True, read_only=True)
    promoted_services = ServicesSerializer(many=True, read_only=True)
    products = ProductsSerializer(many=True, read_only=True)
    services = ServicesSerializer(many=True, read_only=True)
    filter_options = serializers.DictField(read_only=True)
    applied_filters = serializers.DictField(read_only=True)
    total_results = serializers.DictField(read_only=True)


class StatsSerializer(serializers.Serializer):
    total_products = serializers.IntegerField()
    published_products = serializers.IntegerField()
    pending_products = serializers.IntegerField()
    total_services = serializers.IntegerField()
    published_services = serializers.IntegerField()
    pending_services = serializers.IntegerField()
    total_product_ratings = serializers.IntegerField()
    total_service_ratings = serializers.IntegerField()
    top_locations = serializers.ListField(read_only=True)
    top_categories = serializers.ListField(read_only=True)


# ===========================
#  SEARCH SERIALIZERS
# ===========================

class SearchSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, max_length=200, allow_blank=True)
    category = serializers.CharField(required=False, max_length=100, allow_blank=True)
    location = serializers.CharField(required=False, max_length=100, allow_blank=True)
    min_price = serializers.DecimalField(required=False, max_digits=10, decimal_places=2, min_value=0)
    max_price = serializers.DecimalField(required=False, max_digits=10, decimal_places=2, min_value=0)
    min_rating = serializers.DecimalField(required=False, max_digits=2, decimal_places=1, min_value=1.0, max_value=5.0)
    item_type = serializers.ChoiceField(
        choices=[('all', 'All'), ('products', 'Products'), ('services', 'Services')],
        required=False,
        default='all'
    )
    
    def validate(self, data):
        min_price = data.get('min_price')
        max_price = data.get('max_price')
        
        if min_price and max_price and min_price >= max_price:
            raise serializers.ValidationError("Minimum price must be less than maximum price.")
        
        return data


# ===========================
#  PAYMENT SERIALIZERS
# ===========================

class PaymentInitiateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(required=False)
    service_id = serializers.IntegerField(required=False)
    
    def validate(self, data):
        product_id = data.get('product_id')
        service_id = data.get('service_id')
        
        if not product_id and not service_id:
            raise serializers.ValidationError("Either product_id or service_id is required")
        
        if product_id and service_id:
            raise serializers.ValidationError("Provide either product_id or service_id, not both")
        
        return data


class PaymentVerifySerializer(serializers.Serializer):
    product_id = serializers.IntegerField(required=False)
    service_id = serializers.IntegerField(required=False)
    
    def validate(self, data):
        product_id = data.get('product_id')
        service_id = data.get('service_id')
        
        if not product_id and not service_id:
            raise serializers.ValidationError("Either product_id or service_id is required")
        
        if product_id and service_id:
            raise serializers.ValidationError("Provide either product_id or service_id, not both")
        
        return data


class PaymentCallbackSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=100)
    status = serializers.CharField(max_length=50, required=False)


class PaymentStatusResponseSerializer(serializers.Serializer):
    item_type = serializers.CharField()
    item_id = serializers.IntegerField()
    item_name = serializers.CharField()
    is_paid = serializers.BooleanField()
    status = serializers.CharField()
    is_promoted = serializers.BooleanField()
    promotion_fee = serializers.DecimalField(max_digits=10, decimal_places=2)
    published_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class PaymentHistorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    item_name = serializers.CharField()
    status = serializers.CharField()
    is_promoted = serializers.BooleanField()
    promotion_fee = serializers.DecimalField(max_digits=10, decimal_places=2)
    published_at = serializers.DateTimeField()
    created_at = serializers.DateTimeField()


class PaymentSummarySerializer(serializers.Serializer):
    total_payments = serializers.IntegerField()
    total_products_paid = serializers.IntegerField()
    total_services_paid = serializers.IntegerField()
    total_amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2)
    base_listing_fee = serializers.DecimalField(max_digits=10, decimal_places=2)


class PromotionPaymentSerializer(serializers.Serializer):
    item_type = serializers.ChoiceField(choices=['product', 'service'])
    item_id = serializers.IntegerField(validators=[MinValueValidator(1)])
    promotion_duration = serializers.IntegerField(
        default=30, 
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        help_text="Promotion duration in days (1-365)"
    )


# ===========================
#  BULK OPERATION SERIALIZERS
# ===========================

class BulkOperationSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=[
        ('delete', 'Delete'),
        ('publish', 'Publish'),
        ('draft', 'Set to Draft'),
        ('feature', 'Feature'),
        ('unfeature', 'Remove Feature'),
    ])
    item_type = serializers.ChoiceField(choices=['products', 'services'])
    item_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=100  # Limit bulk operations
    )


# ===========================
#  ANALYTICS SERIALIZERS
# ===========================

class TrendingSearchSerializer(serializers.Serializer):
    search_term = serializers.CharField()
    search_count = serializers.IntegerField()
    avg_results = serializers.FloatField()


class PopularCategorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    icon = serializers.CharField()
    products_count = serializers.IntegerField()
    services_count = serializers.IntegerField()
    total_count = serializers.IntegerField()


class UserDashboardSerializer(serializers.Serializer):
    products = serializers.DictField()
    services = serializers.DictField()
    recent_activity = serializers.DictField()
    performance = serializers.DictField()
    recent_products = ProductsSerializer(many=True)
    recent_services = ServicesSerializer(many=True)
    favorites = UserFavoriteSerializer(many=True)


# ===========================
#  EXPORT SERIALIZERS
# ===========================

class ExportDataSerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=[('all', 'All'), ('products', 'Products'), ('services', 'Services'), ('ratings', 'Ratings')],
        default='all'
    )
    format = serializers.ChoiceField(
        choices=[('json', 'JSON'), ('csv', 'CSV')],
        default='json'
    )