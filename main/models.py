# models.py - Enhanced Location Models
from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator
from cloudinary.models import CloudinaryField
import uuid
from django.utils.text import slugify

# ===========================
#  ENHANCED LOCATION MODELS
# ===========================

class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=3, unique=True, help_text="ISO country code (e.g., US, NG, GB)")
    phone_code = models.CharField(max_length=10, blank=True, null=True, help_text="Country calling code (e.g., +1, +234)")
    currency_code = models.CharField(max_length=3, blank=True, null=True, help_text="ISO currency code (e.g., USD, NGN)")
    currency_symbol = models.CharField(max_length=5, blank=True, null=True, help_text="Currency symbol (e.g., $, ₦)")
    flag_emoji = models.CharField(max_length=10, blank=True, null=True)
    continent = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = "Countries"
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active', 'sort_order']),
        ]
    
    def __str__(self):
        return f"{self.flag_emoji} {self.name}" if self.flag_emoji else self.name
    
    def get_display_name(self):
        return f"{self.name} ({self.code})"


class State(models.Model):
    name = models.CharField(max_length=100)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='states')
    code = models.CharField(max_length=10, blank=True, null=True, help_text="State/Province code")
    type = models.CharField(max_length=20, default='state', choices=[
        ('state', 'State'),
        ('province', 'Province'),
        ('region', 'Region'),
        ('territory', 'Territory'),
        ('district', 'District'),
    ])
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['sort_order', 'name']
        unique_together = ('name', 'country')
        indexes = [
            models.Index(fields=['country', 'is_active']),
            models.Index(fields=['code']),
        ]
    
    def __str__(self):
        return f"{self.name}, {self.country.name}"
    
    def get_display_name(self):
        return f"{self.name} ({self.code})" if self.code else self.name


class City(models.Model):
    name = models.CharField(max_length=100)
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='cities')
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='cities')
    latitude = models.DecimalField(max_digits=10, decimal_places=8, blank=True, null=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, blank=True, null=True)
    population = models.PositiveIntegerField(blank=True, null=True)
    timezone = models.CharField(max_length=50, blank=True, null=True)
    is_capital = models.BooleanField(default=False)
    is_major_city = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['sort_order', 'name']
        unique_together = ('name', 'state', 'country')
        verbose_name_plural = "Cities"
        indexes = [
            models.Index(fields=['state', 'is_active']),
            models.Index(fields=['country', 'is_major_city']),
            models.Index(fields=['is_capital']),
        ]
    
    def __str__(self):
        return f"{self.name}, {self.state.name}, {self.country.name}"
    
    def get_full_address(self):
        return f"{self.name}, {self.state.name}, {self.country.name}"


# ===========================
#  ENHANCED CATEGORY MODEL
# ===========================

class Category(models.Model):
    CATEGORY_TYPE_CHOICES = [
        ('product', 'Product Category'),
        ('service', 'Service Category'),
        ('both', 'Both Products & Services'),
    ]
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True, null=True)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPE_CHOICES, default='both')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True, related_name='subcategories')
    icon = models.CharField(max_length=50, blank=True, null=True, help_text="CSS icon class or emoji")
    image = CloudinaryField('category_images', blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = "Categories"
        indexes = [
            models.Index(fields=['category_type', 'is_active']),
            models.Index(fields=['parent', 'is_active']),
            models.Index(fields=['is_featured']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
    
    def get_full_path(self):
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.name}"
        return self.name
    
    def get_children(self):
        return self.subcategories.filter(is_active=True).order_by('sort_order', 'name')
    
    def get_all_products(self):
        """Get all products in this category and subcategories"""
        categories = [self]
        categories.extend(self.get_all_subcategories())
        return Products.objects.filter(category__in=categories, product_status='published')
    
    def get_all_subcategories(self):
        """Recursively get all subcategories"""
        subcategories = list(self.subcategories.filter(is_active=True))
        for subcat in list(subcategories):
            subcategories.extend(subcat.get_all_subcategories())
        return subcategories


# ===========================
#  ENHANCED PRODUCTS MODEL
# ===========================

class Products(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Payment'),
        ('published', 'Published'),
        ('suspended', 'Suspended'),
        ('sold', 'Sold'),
        ('expired', 'Expired'),
    ]
    
    CONDITION_CHOICES = [
        ('new', 'Brand New'),
        ('used', 'Used'),
        ('refurbished', 'Refurbished'),
    ]
    
    # Basic Information
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="products")
    product_name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    product_description = models.TextField(max_length=3000)
    
    # Images
    featured_image = CloudinaryField('product_images/featured')

    # Use JSONField to store multiple Cloudinary URLs
    gallery_images = models.JSONField(default=list, blank=True, help_text="Store multiple Cloudinary URLs")
    
    def save_gallery_images(self, cloudinary_urls):
        """Helper method to save gallery images"""
        self.gallery_images = cloudinary_urls
        self.save()

    
    # Pricing
    product_price = models.DecimalField(max_digits=15, decimal_places=2)
    original_price = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=3, default='NGN')
    is_negotiable = models.BooleanField(default=True)
    
    # Location (Foreign Keys)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='products')
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='products')
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='products')
    address_details = models.CharField(max_length=200, blank=True, null=True)
    
    # Category
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    tags = models.CharField(max_length=500, blank=True, null=True, help_text="Comma-separated tags")
    
    # Product Details
    product_brand = models.CharField(max_length=200, blank=True, null=True)
    product_model = models.CharField(max_length=200, blank=True, null=True)
    product_condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='new')
    product_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Contact Information
    provider_phone = models.CharField(max_length=20, validators=[
        RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be valid")
    ])
    provider_email = models.EmailField(blank=True, null=True)
    provider_whatsapp = models.CharField(max_length=20, blank=True, null=True)
    
    # Business Features
    is_paid = models.BooleanField(default=False)
    is_promoted = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    promotion_fee = models.DecimalField(max_digits=10, decimal_places=2, default=10.00)
    views_count = models.PositiveIntegerField(default=0)
    favorites_count = models.PositiveIntegerField(default=0)
    
    # SEO
    meta_title = models.CharField(max_length=160, blank=True, null=True)
    meta_description = models.CharField(max_length=320, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-is_promoted', '-is_featured', '-created_at']
        verbose_name_plural = "Products"
        indexes = [
            models.Index(fields=['product_status', 'is_promoted', 'is_featured']),
            models.Index(fields=['category', 'country', 'state', 'city']),
            models.Index(fields=['created_at']),
            models.Index(fields=['slug']),
            models.Index(fields=['user', 'product_status']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = f"{slugify(self.product_name)}-{uuid.uuid4().hex[:8]}"
        
        # Auto-set currency based on country
        if not self.currency and self.country and self.country.currency_code:
            self.currency = self.country.currency_code
            
        super().save(*args, **kwargs)
    
    def get_currency_symbol(self):
        return self.country.currency_symbol if self.country and self.country.currency_symbol else '$'
    
    def get_formatted_price(self):
        symbol = self.get_currency_symbol()
        return f"{symbol}{self.product_price:,.2f}"
    
    def get_discount_percentage(self):
        if self.original_price and self.original_price > self.product_price:
            return round(((self.original_price - self.product_price) / self.original_price) * 100)
        return 0
    
    def average_rating(self):
        ratings = self.product_ratings.filter(is_active=True)
        if ratings.exists():
            return round(sum(float(r.rating) for r in ratings) / ratings.count(), 1)
        return 0
    
    def rating_count(self):
        return self.product_ratings.filter(is_active=True).count()
    
    def get_absolute_url(self):
        return f"/products/{self.slug}/"
    
    def get_full_location(self):
        return f"{self.city.name}, {self.state.name}, {self.country.name}"
    
    def increment_views(self):
        self.views_count += 1
        self.save(update_fields=['views_count'])
    
    def get_tags_list(self):
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []
    
    def __str__(self):
        return f"{self.product_name} - {self.city.name}, {self.state.name}"


# ===========================
#  ENHANCED SERVICES MODEL
# ===========================

class Services(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Payment'),
        ('published', 'Published'),
        ('suspended', 'Suspended'),
        ('unavailable', 'Unavailable'),
        ('expired', 'Expired'),
    ]
    
    EXPERIENCE_CHOICES = [
        ('beginner', '0-1 years'),
        ('intermediate', '1-3 years'),
        ('experienced', '3-5 years'),
        ('expert', '5-10 years'),
        ('master', '10+ years'),
    ]
    
    PRICE_TYPE_CHOICES = [
        ('fixed', 'Fixed Price'),
        ('hourly', 'Per Hour'),
        ('daily', 'Per Day'),
        ('weekly', 'Per Week'),
        ('monthly', 'Per Month'),
        ('project', 'Per Project'),
        ('negotiable', 'Negotiable'),
    ]
    
    # Basic Information
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="services")
    service_name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    service_description = models.TextField(max_length=3000)
    
    # Images
    featured_image = CloudinaryField('service_images/featured')

    # Use JSONField to store multiple Cloudinary URLs
    gallery_images = models.JSONField(default=list, blank=True, help_text="Store multiple Cloudinary URLs")
    
    def save_gallery_images(self, cloudinary_urls):
        """Helper method to save gallery images"""
        self.gallery_images = cloudinary_urls
        self.save()
    
    # Location (Foreign Keys)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='services')
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='services')
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='services')
    serves_remote = models.BooleanField(default=False, help_text="Can provide service remotely")
    service_radius = models.PositiveIntegerField(blank=True, null=True, help_text="Service radius in KM")
    
    # Category
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='services')
    tags = models.CharField(max_length=500, blank=True, null=True)
    
    # Service Provider Information
    provider_name = models.CharField(max_length=200)
    provider_title = models.CharField(max_length=200, blank=True, null=True)
    provider_bio = models.TextField(max_length=1000, blank=True, null=True)
    provider_expertise = models.TextField(max_length=1000)
    provider_experience = models.CharField(max_length=20, choices=EXPERIENCE_CHOICES, default='beginner')
    provider_certifications = models.TextField(max_length=500, blank=True, null=True)
    provider_languages = models.CharField(max_length=200, blank=True, null=True)
    
    # Contact Information
    provider_email = models.EmailField()
    provider_phone = models.CharField(max_length=20, validators=[
        RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be valid")
    ])
    provider_whatsapp = models.CharField(max_length=20, blank=True, null=True)
    provider_website = models.URLField(blank=True, null=True)
    provider_linkedin = models.URLField(blank=True, null=True)
    
    # Pricing
    starting_price = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    max_price = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=3, default='NGN')
    price_type = models.CharField(max_length=20, choices=PRICE_TYPE_CHOICES, default='negotiable')
    
    # Service Details
    service_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    response_time = models.CharField(max_length=50, blank=True, null=True, help_text="e.g., '24 hours', 'Same day'")
    availability = models.CharField(max_length=200, blank=True, null=True)
    
    # Business Features
    is_paid = models.BooleanField(default=False)
    is_promoted = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    promotion_fee = models.DecimalField(max_digits=10, decimal_places=2, default=10.00)
    views_count = models.PositiveIntegerField(default=0)
    contacts_count = models.PositiveIntegerField(default=0)
    
    # SEO
    meta_title = models.CharField(max_length=160, blank=True, null=True)
    meta_description = models.CharField(max_length=320, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-is_promoted', '-is_featured', '-created_at']
        verbose_name_plural = "Services"
        indexes = [
            models.Index(fields=['service_status', 'is_promoted', 'is_featured']),
            models.Index(fields=['category', 'country', 'state', 'city']),
            models.Index(fields=['created_at']),
            models.Index(fields=['slug']),
            models.Index(fields=['user', 'service_status']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = f"{slugify(self.service_name)}-{uuid.uuid4().hex[:8]}"
        
        if not self.currency and self.country and self.country.currency_code:
            self.currency = self.country.currency_code
            
        super().save(*args, **kwargs)
    
    def get_currency_symbol(self):
        return self.country.currency_symbol if self.country and self.country.currency_symbol else '$'
    
    def get_formatted_price_range(self):
        symbol = self.get_currency_symbol()
        if self.starting_price and self.max_price:
            return f"{symbol}{self.starting_price:,.2f} - {symbol}{self.max_price:,.2f}"
        elif self.starting_price:
            return f"From {symbol}{self.starting_price:,.2f}"
        return "Contact for pricing"
    
    def average_rating(self):
        ratings = self.service_ratings.filter(is_active=True)
        if ratings.exists():
            return round(sum(float(r.rating) for r in ratings) / ratings.count(), 1)
        return 0
    
    def rating_count(self):
        return self.service_ratings.filter(is_active=True).count()
    
    def get_absolute_url(self):
        return f"/services/{self.slug}/"
    
    def get_full_location(self):
        return f"{self.city.name}, {self.state.name}, {self.country.name}"
    
    def increment_views(self):
        self.views_count += 1
        self.save(update_fields=['views_count'])
    
    def increment_contacts(self):
        self.contacts_count += 1
        self.save(update_fields=['contacts_count'])
    
    def get_tags_list(self):
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []
    
    def __str__(self):
        return f"{self.service_name} by {self.provider_name} - {self.city.name}"


# ===========================
#  ENHANCED RATING MODELS
# ===========================

class ProductRating(models.Model):
    product = models.ForeignKey(Products, on_delete=models.CASCADE, related_name="product_ratings")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.DecimalField(max_digits=2, decimal_places=1, choices=[
        (1.0, '1.0'), (1.5, '1.5'), (2.0, '2.0'), (2.5, '2.5'), (3.0, '3.0'),
        (3.5, '3.5'), (4.0, '4.0'), (4.5, '4.5'), (5.0, '5.0')
    ])
    review_title = models.CharField(max_length=200, blank=True, null=True)
    review = models.TextField(max_length=1500, blank=True, null=True)
    pros = models.TextField(max_length=500, blank=True, null=True)
    cons = models.TextField(max_length=500, blank=True, null=True)
    would_recommend = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    is_verified_purchase = models.BooleanField(default=False)
    helpful_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('product', 'user')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'is_active']),
            models.Index(fields=['rating']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.rating}⭐ for {self.product.product_name}"


class ServiceRating(models.Model):
    service = models.ForeignKey(Services, on_delete=models.CASCADE, related_name="service_ratings")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.DecimalField(max_digits=2, decimal_places=1, choices=[
        (1.0, '1.0'), (1.5, '1.5'), (2.0, '2.0'), (2.5, '2.5'), (3.0, '3.0'),
        (3.5, '3.5'), (4.0, '4.0'), (4.5, '4.5'), (5.0, '5.0')
    ])
    review_title = models.CharField(max_length=200, blank=True, null=True)
    review = models.TextField(max_length=1500, blank=True, null=True)
    communication_rating = models.DecimalField(max_digits=2, decimal_places=1, blank=True, null=True, choices=[
        (1.0, '1.0'), (1.5, '1.5'), (2.0, '2.0'), (2.5, '2.5'), (3.0, '3.0'),
        (3.5, '3.5'), (4.0, '4.0'), (4.5, '4.5'), (5.0, '5.0')
    ])
    quality_rating = models.DecimalField(max_digits=2, decimal_places=1, blank=True, null=True, choices=[
        (1.0, '1.0'), (1.5, '1.5'), (2.0, '2.0'), (2.5, '2.5'), (3.0, '3.0'),
        (3.5, '3.5'), (4.0, '4.0'), (4.5, '4.5'), (5.0, '5.0')
    ])
    timeliness_rating = models.DecimalField(max_digits=2, decimal_places=1, blank=True, null=True, choices=[
        (1.0, '1.0'), (1.5, '1.5'), (2.0, '2.0'), (2.5, '2.5'), (3.0, '3.0'),
        (3.5, '3.5'), (4.0, '4.0'), (4.5, '4.5'), (5.0, '5.0')
    ])
    would_recommend = models.BooleanField(default=True)
    would_hire_again = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    is_verified_customer = models.BooleanField(default=False)
    helpful_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('service', 'user')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['service', 'is_active']),
            models.Index(fields=['rating']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.rating}⭐ for {self.service.service_name}"


# ===========================
#  UTILITY MODELS
# ===========================

class UserFavorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(Products, on_delete=models.CASCADE, blank=True, null=True)
    service = models.ForeignKey(Services, on_delete=models.CASCADE, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [('user', 'product'), ('user', 'service')]
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]


class SearchHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    search_term = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, blank=True, null=True)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, blank=True, null=True)
    state = models.ForeignKey(State, on_delete=models.CASCADE, blank=True, null=True)
    city = models.ForeignKey(City, on_delete=models.CASCADE, blank=True, null=True)
    search_type = models.CharField(max_length=20, choices=[
        ('product', 'Product'),
        ('service', 'Service'),
        ('both', 'Both'),
    ], default='both')
    results_count = models.PositiveIntegerField(default=0)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['search_term', 'created_at']),
            models.Index(fields=['country', 'state', 'city']),
            models.Index(fields=['user', 'created_at']),
        ]


class LocationCache(models.Model):
    cache_key = models.CharField(max_length=200, unique=True)
    cache_data = models.JSONField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['cache_key', 'expires_at']),
        ]