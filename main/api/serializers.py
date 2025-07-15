from rest_framework import serializers
from ..models import (
    LocationCategory,
    Products,
    Services,
    ProductRating,
    ServiceRating
)

class LocationCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationCategory
        fields = "__all__"

class ProductRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductRating
        fields = [
            "id", "user", "user_name", "rating", 
            "review", "created_at"
        ]

class ServiceRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceRating
        fields = [
            "id", "user", "user_name", "rating", 
            "review", "created_at"
        ]

class ProductsSerializer(serializers.ModelSerializer):
    average_rating  = serializers.ReadOnlyField()
    rating_count    = serializers.ReadOnlyField()
    product_ratings = ProductRatingSerializer(many=True, read_only=True)

    class Meta:
        model = Products
        fields = [
            "id", "user", "product_name", "product_image",
            "product_description", "product_price",
            "product_category", "product_country",
            "product_state", "product_city", "product_brand",
            "product_provider_phone", "product_status",
            "is_paid", "is_promoted", "promotion_fee",
            "average_rating", "rating_count", "product_ratings",
        ]

class ServicesSerializer(serializers.ModelSerializer):
    average_rating   = serializers.ReadOnlyField()
    rating_count     = serializers.ReadOnlyField()
    service_ratings  = ServiceRatingSerializer(many=True, read_only=True)

    class Meta:
        model = Services
        fields = [
            "id", "user", "service_name", "service_image",
            "service_description", "service_category",
            "service_country", "service_state", "service_city",
            "service_provider_name", "service_provider_expertise",
            "service_provider_experience_year", "service_provider_email",
            "service_provider_phone", "service_status",
            "is_paid", "is_promoted", "promotion_fee",
            "average_rating", "rating_count", "service_ratings",
        ]
