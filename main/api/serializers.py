# api/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..models import (
    LocationCategory,
    Products,
    Services,
    ProductRating,
    ServiceRating
)

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']

class LocationCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationCategory
        fields = "__all__"

class ProductRatingSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = ProductRating
        fields = [
            "id", "user", "user_details", "user_name", 
            "rating", "review", "created_at"
        ]
        read_only_fields = ['user', 'created_at']

class ServiceRatingSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = ServiceRating
        fields = [
            "id", "user", "user_details", "user_name", 
            "rating", "review", "created_at"
        ]
        read_only_fields = ['user', 'created_at']

class ProductsSerializer(serializers.ModelSerializer):
    average_rating = serializers.ReadOnlyField()
    rating_count = serializers.ReadOnlyField()
    product_ratings = ProductRatingSerializer(many=True, read_only=True)
    user_details = UserSerializer(source='user', read_only=True)
    
    # Add choices for frontend dropdowns
    category_choices = serializers.SerializerMethodField()
    country_choices = serializers.SerializerMethodField()
    state_choices = serializers.SerializerMethodField()
    city_choices = serializers.SerializerMethodField()
    status_choices = serializers.SerializerMethodField()
    
    class Meta:
        model = Products
        fields = [
            "id", "user", "user_details", "product_name", "product_image",
            "product_description", "product_price", "product_category",
            "product_country", "product_state", "product_city", "product_brand",
            "product_provider_phone", "product_status", "is_paid", "is_promoted",
            "promotion_fee", "average_rating", "rating_count", "product_ratings",
            "category_choices", "country_choices", "state_choices", "city_choices",
            "status_choices"
        ]
        read_only_fields = ['user', 'average_rating', 'rating_count', 'product_ratings']
    
    def get_category_choices(self, obj):
        return LocationCategory.CATEGORY_CHOICES
    
    def get_country_choices(self, obj):
        return LocationCategory.COUNTRY_CHOICES
    
    def get_state_choices(self, obj):
        return LocationCategory.STATE_CHOICES
    
    def get_city_choices(self, obj):
        return LocationCategory.CITY_CHOICES
    
    def get_status_choices(self, obj):
        return LocationCategory.STATUS_CHOICES

class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Products
        fields = [
            "product_name", "product_image", "product_description",
            "product_price", "product_category", "product_country",
            "product_state", "product_city", "product_brand",
            "product_provider_phone", "is_promoted"
        ]
    
    def validate_product_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value
    
    def validate_product_name(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Product name must be at least 3 characters long.")
        return value.strip()

class ServicesSerializer(serializers.ModelSerializer):
    average_rating = serializers.ReadOnlyField()
    rating_count = serializers.ReadOnlyField()
    service_ratings = ServiceRatingSerializer(many=True, read_only=True)
    user_details = UserSerializer(source='user', read_only=True)
    
    # Add choices for frontend dropdowns
    category_choices = serializers.SerializerMethodField()
    country_choices = serializers.SerializerMethodField()
    state_choices = serializers.SerializerMethodField()
    city_choices = serializers.SerializerMethodField()
    status_choices = serializers.SerializerMethodField()
    
    class Meta:
        model = Services
        fields = [
            "id", "user", "user_details", "service_name", "service_image",
            "service_description", "service_category", "service_country",
            "service_state", "service_city", "service_provider_name",
            "service_provider_expertise", "service_provider_experience_year",
            "service_provider_email", "service_provider_phone", "service_status",
            "other_service_a", "other_service_b", "other_service_c",
            "is_paid", "is_promoted", "promotion_fee", "average_rating",
            "rating_count", "service_ratings", "category_choices",
            "country_choices", "state_choices", "city_choices", "status_choices"
        ]
        read_only_fields = ['user', 'average_rating', 'rating_count', 'service_ratings']
    
    def get_category_choices(self, obj):
        return LocationCategory.CATEGORY_CHOICES
    
    def get_country_choices(self, obj):
        return LocationCategory.COUNTRY_CHOICES
    
    def get_state_choices(self, obj):
        return LocationCategory.STATE_CHOICES
    
    def get_city_choices(self, obj):
        return LocationCategory.CITY_CHOICES
    
    def get_status_choices(self, obj):
        return LocationCategory.STATUS_CHOICES

class ServiceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Services
        fields = [
            "service_name", "service_image", "service_description",
            "service_category", "service_country", "service_state",
            "service_city", "service_provider_name", "service_provider_expertise",
            "service_provider_experience_year", "service_provider_email",
            "service_provider_phone", "other_service_a", "other_service_b",
            "other_service_c", "is_promoted"
        ]
    
    def validate_service_name(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Service name must be at least 3 characters long.")
        return value.strip()
    
    def validate_service_provider_email(self, value):
        if '@' not in value:
            raise serializers.ValidationError("Enter a valid email address.")
        return value.lower()
    
    def validate_service_provider_experience_year(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Experience years cannot be negative.")
        return value

class HomePageSerializer(serializers.Serializer):
    promoted_products = ProductsSerializer(many=True, read_only=True)
    promoted_services = ServicesSerializer(many=True, read_only=True)
    products = ProductsSerializer(many=True, read_only=True)
    services = ServicesSerializer(many=True, read_only=True)
    filter_options = serializers.DictField(read_only=True)
    applied_filters = serializers.DictField(read_only=True)

class StatsSerializer(serializers.Serializer):
    total_products = serializers.IntegerField()
    published_products = serializers.IntegerField()
    pending_products = serializers.IntegerField()
    total_services = serializers.IntegerField()
    published_services = serializers.IntegerField()
    pending_services = serializers.IntegerField()
    total_product_ratings = serializers.IntegerField()
    total_service_ratings = serializers.IntegerField()

# For bulk operations
class BulkProductUpdateSerializer(serializers.Serializer):
    product_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    action = serializers.ChoiceField(choices=[
        ('promote', 'Promote'),
        ('unpromote', 'Unpromote'),
        ('delete', 'Delete'),
        ('publish', 'Publish'),
        ('unpublish', 'Unpublish')
    ])

class BulkServiceUpdateSerializer(serializers.Serializer):
    service_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    action = serializers.ChoiceField(choices=[
        ('promote', 'Promote'),
        ('unpromote', 'Unpromote'),
        ('delete', 'Delete'),
        ('publish', 'Publish'),
        ('unpublish', 'Unpublish')
    ])

# For payment
class PaymentInitiateSerializer(serializers.Serializer):
    item_type = serializers.ChoiceField(choices=[('product', 'Product'), ('service', 'Service')])
    item_id = serializers.IntegerField()
    
    def validate_item_id(self, value):
        if value <= 0:
            raise serializers.ValidationError("Item ID must be a positive integer.")
        return value

class PaymentVerifySerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=100)
    
    def validate_reference(self, value):
        if not value.strip():
            raise serializers.ValidationError("Reference cannot be empty.")
        return value.strip()

# For advanced search
class SearchSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, max_length=200)
    category = serializers.CharField(required=False, max_length=100)
    location = serializers.CharField(required=False, max_length=100)
    min_price = serializers.DecimalField(required=False, max_digits=10, decimal_places=2)
    max_price = serializers.DecimalField(required=False, max_digits=10, decimal_places=2)
    min_rating = serializers.DecimalField(required=False, max_digits=2, decimal_places=1)
    item_type = serializers.ChoiceField(
        choices=[('all', 'All'), ('products', 'Products'), ('services', 'Services')],
        required=False,
        default='all'
    )