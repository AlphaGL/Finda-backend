from django.db import models
# from django.contrib.auth.models import User  # For customer ratings
from django.conf import settings # Custom User Authentication
from cloudinary.models import CloudinaryField
# ===========================
#  CATEGORY MODEL (LOCATIONS)
# ===========================

class LocationCategory(models.Model):
    CATEGORY_CHOICES = [
        ('all', 'All Categories'),
        ('fitness_services', 'Fitness & Personal Training Services'),
    ]

    COUNTRY_CHOICES = [
        ('NG', 'Nigeria'),
    ]

    STATE_CHOICES = [
        ("All", 'All'),
        ("Abia", "Abia"), ("Adamawa", "Adamawa"), ("Akwa Ibom", "Akwa Ibom"),
        ("Taraba", "Taraba"), ("Yobe", "Yobe"), ("Zamfara", "Zamfara"), ("Abuja", "Abuja")
    ]

    CITY_CHOICES = [
        ("All", 'All'),
        ("Gusau", "Gusau"),
        ("Garki", "Garki"), ("Maitama", "Maitama"), ("Wuse", "Wuse")
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('published', 'Published'),
    ]

    category = models.CharField(max_length=300, choices=CATEGORY_CHOICES)
    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES, default='NG')
    state = models.CharField(max_length=20, choices=STATE_CHOICES)
    city = models.CharField(max_length=50)  # Cities will be dynamically populated in forms
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    class Meta:
        ordering = ['state', 'category']

    def __str__(self):
        return f"{self.get_category_display()} - {self.state} - {self.city}"

    def get_city_choices(self):
        """Returns the list of cities based on the selected state."""

        return self.CITY_CHOICES.get(self.state, [])
# https://youtu.be/H904uD-kGjA?si=hLvC1uWQIF5yHgMF
# ===========================
#  PRODUCTS MODEL
# ===========================
class Products(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="products",default=1)
    product_name = models.CharField(max_length=100)
    product_image = CloudinaryField('product_images')
    product_description = models.TextField(max_length=250)
    product_price = models.PositiveIntegerField()
    product_category = models.CharField(max_length=300, choices=LocationCategory.CATEGORY_CHOICES, default="all")
    product_country = models.CharField(max_length=50, choices=LocationCategory.COUNTRY_CHOICES, default="All")
    product_state = models.CharField(max_length=50, choices=LocationCategory.STATE_CHOICES, default="All")
    product_status = models.CharField(max_length=20, choices=LocationCategory.STATUS_CHOICES, default='pending')
    product_city = models.CharField(max_length=50, choices=LocationCategory.CITY_CHOICES, default="All")
    product_brand = models.CharField(max_length=200)
    # product_provider_email = models.CharField(max_length=1000, null=True, blank=True)
    product_provider_phone = models.CharField(max_length=15, null=True, blank=True)
    is_paid = models.BooleanField(default=False)  # Track payment status

    # Add this to your Products model
    is_promoted = models.BooleanField(default=False)
    promotion_fee = models.PositiveIntegerField(default=1000)


    def average_rating(self):
        ratings = self.product_ratings.all()
        if ratings.exists():
            return round(sum(r.rating for r in ratings) / ratings.count(), 1)
        return 0

    def rating_count(self):
        return self.product_ratings.count()

    def __str__(self):
        return f"{self.product_name} - {self.product_city}, {self.product_state}, {self.product_country}"  # Fixed undefined attribute


# ===========================
#  SERVICES MODEL
# ===========================
class Services(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="services",default=1)
    service_name = models.CharField(max_length=100)
    service_image = CloudinaryField('service_images')
    service_description = models.TextField(max_length=250)
    service_category = models.CharField(max_length=300, choices=LocationCategory.CATEGORY_CHOICES, default="all")
    service_country = models.CharField(max_length=50, choices=LocationCategory.COUNTRY_CHOICES, default="All")
    service_state = models.CharField(max_length=50, choices=LocationCategory.STATE_CHOICES, default="All")
    service_city = models.CharField(max_length=50, choices=LocationCategory.CITY_CHOICES, default="All")

    service_provider_name = models.CharField(max_length=200)
    service_provider_expertise = models.TextField(max_length=500)
    service_provider_experience_year = models.PositiveIntegerField(null=True, blank=True)
    service_provider_email = models.CharField(max_length=1000)
    service_provider_phone = models.CharField(max_length=15)

    service_status = models.CharField(max_length=20, choices=LocationCategory.STATUS_CHOICES, default='pending')

    other_service_a = models.CharField(max_length=50, blank=True, null=True)
    other_service_b = models.CharField(max_length=50, blank=True, null=True)
    other_service_c = models.CharField(max_length=50, blank=True, null=True)

    is_paid = models.BooleanField(default=False)  # Track payment status

    # Add this to your Services model
    is_promoted = models.BooleanField(default=False)
    promotion_fee = models.PositiveIntegerField(default=1000)

    def average_rating(self):
        ratings = self.service_ratings.all()
        if ratings.exists():
            return round(sum(r.rating for r in ratings) / ratings.count(), 1)
        return 0

    def rating_count(self):
        return self.service_ratings.count()

    def __str__(self):
        return f"{self.service_name} - {self.service_city}, {self.service_state}, {self.service_country}"  # Fixed undefined attribute


# ===========================
#  PRODUCT RATING MODEL
# ===========================
class ProductRating(models.Model):
    product = models.ForeignKey(Products, on_delete=models.CASCADE, related_name="product_ratings")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    user_name = models.CharField(max_length=250, blank=False, default='anonymous')
    rating = models.DecimalField(max_digits=2, decimal_places=1, choices=[(i/2, str(i/2)) for i in range(0, 11)])
    review = models.TextField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'user')

    def __str__(self):
        return f"{self.user.username} - {self.rating}⭐ - for {self.product.product_name}"


# ===========================
#  SERVICE RATING MODEL
# ===========================
class ServiceRating(models.Model):
    service = models.ForeignKey(Services, on_delete=models.CASCADE, related_name="service_ratings")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE) # custom user authentication
    user_name = models.CharField(max_length=250, blank=False, default='anonymous')
    rating = models.DecimalField(max_digits=2, decimal_places=1, choices=[(i/2, str(i/2)) for i in range(0, 11)])
    review = models.TextField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('service', 'user')

    def __str__(self):
        return f"{self.user.username} - {self.rating}⭐ for {self.service.service_name}"