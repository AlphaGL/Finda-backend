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
        ('activism', 'Activism & Social Movements'),
        ('advertising_services', 'Advertising & Marketing Services'),
        ('ai', 'Artificial Intelligence'),
        ('antiques', 'Antiques'),
        ('astronomy', 'Astronomy & Astrophysics'),
        ('automobile', 'Automobiles'),
        ('automobiles', 'Vehicles'),
        ('automotive', 'Automotive Repair & Maintenance'),
        ('biking', 'Biking & Cycling'),
        ('biology', 'Biology'),
        ('blockchain', 'Blockchain Technology'),
        ('book_clubs', 'Book Clubs & Reviews'),
        ('business', 'Business'),
        ('business_automation', 'Business Automation & CRM'),
        ('camping', 'Camping & Survival Skills'),
        ('cars', 'Cars & Automotive Reviews'),
        ('chemistry', 'Chemistry'),
        ('cloud_computing', 'Cloud Computing'),
        ('cloud_services', 'Cloud Services & Hosting'),
        ('collectibles', 'Collectibles & Memorabilia'),
        ('comedy', 'Comedy & Stand-Up'),
        ('composting', 'Composting & Waste Management'),
        ('construction', 'Construction & Building Materials'),
        ('consulting_services', 'Business & Consulting Services'),
        ('cycling', 'Cycling & Mountain Biking'),
        ('digital_marketing', 'Digital Marketing & SEO'),
        ('digital_marketing_services', 'Digital Marketing & SEO Services'),
        ('disability', 'Disability Rights & Support'),
        ('diy_projects', 'DIY Projects & Home Improvement'),
        ('education', 'Education'),
        ('education_services', 'Educational Services'),
        ('elderly_care', 'Elderly Care & Support'),
        ('electronics', 'Consumer Electronics'),
        ('electronics', 'Electronics & Gadgets'),
        ('engineering', 'Engineering'),
        ('environment', 'Environment & Sustainability'),
        ('esoteric', 'Esoteric & Mysticism'),
        ('e_sports', 'E-Sports'),
        ('fashion', 'Fashion & Beauty'),
        ('fishing', 'Fishing & Aquatic Sports'),
        ('fitness_services', 'Fitness & Personal Training Services'),
        ('food', 'Food & Cooking'),
        ('food_science', 'Food Science & Research'),
        ('freelancing', 'Freelancing & Remote Work'),
        ('furniture', 'Furniture & Home Decor'),
        ('games', 'Video Games & Consoles'),
        ('gaming', 'Gaming'),
        ('gaming_hardware', 'Gaming Hardware & Equipment'),
        ('gaming_tournaments', 'Gaming Tournaments'),
        ('gardening', 'Gardening'),
        ('gardening_tips', 'Gardening & Landscaping Tips'),
        ('geocaching', 'Geocaching & Treasure Hunting'),
        ('geography', 'Geography'),
        ('genetics', 'Genetics & Genomics'),
        ('graphic_design', 'Graphic Design'),
        ('health_and_beauty', 'Health & Beauty Products'),
        ('health_services', 'Healthcare Services'),
        ('hiking', 'Hiking & Outdoor Activities'),
        ('history', 'History'),
        ('horse_racing', 'Horse Racing & Equestrian Sports'),
        ('humor', 'Humor & Satire'),
        ('internet_of_things', 'Internet of Things (IoT)'),
        ('it_services', 'IT Support & Solutions'),
        ('it_support', 'IT Support & Services'),
        ('jazz', 'Jazz Music'),
        ('jewelry', 'Jewelry & Accessories'),
        ('journalism', 'Journalism'),
        ('kitchenware', 'Kitchen Tools & Appliances'),
        ('language_arts', 'Language Arts'),
        ('language_learning', 'Language Learning'),
        ('leadership', 'Leadership & Management'),
        ('literature', 'Literature'),
        ('literature_reviews', 'Literature Reviews'),
        ('luxury', 'Luxury & Lifestyle'),
        ('luxury_goods', 'Luxury Goods'),
        ('mental_health', 'Mental Health'),
        ('mobile_technology', 'Mobile Technology'),
        ('mobiles', 'Mobile Phones & Accessories'),
        ('motorsports', 'Motorsports & Racing'),
        ('music', 'Music'),
        ('music_production', 'Music Production & Sound Engineering'),
        ('manga', 'Manga & Anime'),
        ('minimalism', 'Minimalism & Decluttering'),
        ('mindfulness', 'Mindfulness & Meditation'),
        ('mobile_technology', 'Mobile Technology'),
        ('movies', 'Movies & TV Shows'),
        ('news', 'News & Media'),
        ('nutrition', 'Nutrition & Diet'),
        ('office_supplies', 'Office Supplies & Equipment'),
        ('pets', 'Pets & Animals'),
        ('pet_supplies', 'Pet Products & Supplies'),
        ('philosophy', 'Philosophy'),
        ('photography', 'Photography'),
        ('photography_services', 'Photography & Videography Services'),
        ('podcasting', 'Podcasting'),
        ('politics', 'Politics & Government'),
        ('personal_growth', 'Personal Growth & Self-Development'),
        ('personal_services', 'Personal Assistance'),
        ('personal_finance', 'Personal Finance'),
        ('programming', 'Programming & Coding'),
        ('product_reviews', 'Product Reviews & Testing'),
        ('productivity', 'Productivity & Self-Improvement'),
        ('real_estate', 'Real Estate'),
        ('real_estate_services', 'Real Estate Services'),
        ('real_estate_investment', 'Real Estate Investment'),
        ('religion', 'Religion & Spirituality'),
        ('rock', 'Rock Music'),
        ('robotics', 'Robotics'),
        ('rock_climbing', 'Rock Climbing & Adventure Sports'),
        ('sailing', 'Sailing & Marine Activities'),
        ('self_defense', 'Self Defense & Safety'),
        ('short_films', 'Short Films & Documentaries'),
        ('snow_sports', 'Snow Sports'),
        ('snowboarding', 'Snowboarding & Skiing'),
        ('social_media', 'Social Media & Marketing'),
        ('space', 'Space Exploration'),
        ('space_technology', 'Space Technology & Exploration'),
        ('sports', 'Sports'),
        ('sports_gear', 'Sports Gear & Equipment'),
        ('stand_up_paddleboarding', 'Stand-Up Paddleboarding'),
        ('skateboarding', 'Skateboarding'),
        ('startups', 'Startups'),
        ('swimming', 'Swimming & Water Sports'),
        ('tarot', 'Tarot & Divination'),
        ('technology', 'Technology'),
        ('television', 'Television & TV Shows'),
        ('tech_reviews', 'Tech Reviews & Gadgets'),
        ('theater', 'Theater & Performing Arts'),
        ('tv_reviews', 'TV Shows & Reviews'),
        ('vintage', 'Vintage & Collectibles'),
        ('vlogging', 'Vlogging & YouTube'),
        ('wearable_technology', 'Wearable Technology'),
        ('web_development', 'Web Development & Programming'),
        ('women_issues', 'Women\'s Issues'),
        ('wine_and_spirits', 'Wine & Spirits'),
        ('yoga', 'Yoga & Meditation'),
        # Product Categories
        ('appliances', 'Home Appliances'),
        ('automobiles', 'Vehicles'),
        ('clothing', 'Apparel & Fashion'),
        ('computers', 'Computer Hardware & Peripherals'),
        ('electronics', 'Consumer Electronics'),
        ('furniture', 'Furniture & Home Decor'),
        ('games', 'Video Games & Consoles'),
        ('health_and_beauty', 'Health & Beauty Products'),
        ('home_decor', 'Home Decor & Accessories'),
        ('jewelry', 'Jewelry & Accessories'),
        ('kitchenware', 'Kitchen Tools & Appliances'),
        ('luxury_goods', 'Luxury Goods'),
        ('mobile_phones', 'Mobile Phones & Accessories'),
        ('office_supplies', 'Office Supplies & Equipment'),
        ('pet_supplies', 'Pet Products & Supplies'),
        ('sports_equipment', 'Sports Equipment & Gear'),
        ('toys_and_games', 'Toys & Games for Kids'),
        ('tools', 'Tools & DIY Products'),
        ('watches', 'Watches & Timepieces'),
        ('wine_and_spirits', 'Wine & Spirits'),
        ('baby_products', 'Baby Products & Accessories'),
        # Service Categories
        ('advertising_services', 'Advertising & Marketing Services'),
        ('cloud_services', 'Cloud Services & Hosting'),
        ('consulting_services', 'Business & Consulting Services'),
        ('education_services', 'Educational Services'),
        ('event_management', 'Event Planning & Management'),
        ('financial_services', 'Financial & Investment Services'),
        ('health_services', 'Healthcare Services'),
        ('home_services', 'Home Improvement Services'),
        ('insurance_services', 'Insurance Services'),
        ('it_services', 'IT Support & Solutions'),
        ('legal_services', 'Legal Consulting & Services'),
        ('real_estate_services', 'Real Estate Services'),
        ('transportation_services', 'Transportation & Delivery Services'),
        ('travel_services', 'Travel & Tourism Services'),
        ('writing_services', 'Writing & Editing Services'),
        ('personal_services', 'Personal Assistance'),
        ('marketing_services', 'Digital Marketing & SEO Services'),
        ('photography_services', 'Photography & Videography Services'),
        ('cleaning_services', 'Cleaning & Janitorial Services'),
        ('fitness_services', 'Fitness & Personal Training Services'),
    ]

    COUNTRY_CHOICES = [
        ('NG', 'Nigeria'),
    ]

    STATE_CHOICES = [
        ("All", 'All'),
        ("Abia", "Abia"), ("Adamawa", "Adamawa"), ("Akwa Ibom", "Akwa Ibom"),
        ("Anambra", "Anambra"), ("Bauchi", "Bauchi"), ("Bayelsa", "Bayelsa"),
        ("Benue", "Benue"), ("Borno", "Borno"), ("Cross River", "Cross River"),
        ("Delta", "Delta"), ("Ebonyi", "Ebonyi"), ("Edo", "Edo"), ("Ekiti", "Ekiti"),
        ("Enugu", "Enugu"), ("Gombe", "Gombe"), ("Imo", "Imo"), ("Jigawa", "Jigawa"),
        ("Kaduna", "Kaduna"), ("Kano", "Kano"), ("Katsina", "Katsina"), ("Kebbi", "Kebbi"),
        ("Kogi", "Kogi"), ("Kwara", "Kwara"), ("Lagos", "Lagos"), ("Nasarawa", "Nasarawa"),
        ("Niger", "Niger"), ("Ogun", "Ogun"), ("Ondo", "Ondo"), ("Osun", "Osun"),
        ("Oyo", "Oyo"), ("Plateau", "Plateau"), ("Rivers", "Rivers"), ("Sokoto", "Sokoto"),
        ("Taraba", "Taraba"), ("Yobe", "Yobe"), ("Zamfara", "Zamfara"), ("Abuja", "Abuja")
    ]

    CITY_CHOICES = [
        ("All", 'All'),
        ("Aba", "Aba"), ("Umuahia", "Umuahia"),
        ("Yola", "Yola"), ("Mubi", "Mubi"),
        ("Uyo", "Uyo"), ("Eket", "Eket"),
        ("Awka", "Awka"), ("Onitsha", "Onitsha"), ("Nnewi", "Nnewi"),
        ("Bauchi", "Bauchi"), ("Azare", "Azare"),
        ("Yenagoa", "Yenagoa"),
        ("Makurdi", "Makurdi"), ("Otukpo", "Otukpo"),
        ("Maiduguri", "Maiduguri"), ("Biu", "Biu"),
        ("Calabar", "Calabar"), ("Ikom", "Ikom"),
        ("Warri", "Warri"), ("Asaba", "Asaba"), ("Sapele", "Sapele"),
        ("Abakaliki", "Abakaliki"),
        ("Benin City", "Benin City"), ("Auchi", "Auchi"),
        ("Ado Ekiti", "Ado Ekiti"),
        ("Enugu", "Enugu"), ("Nsukka", "Nsukka"),
        ("Gombe", "Gombe"),
        ("Owerri", "Owerri"), ("Orlu", "Orlu"),
        ("Dutse", "Dutse"),
        ("Kaduna", "Kaduna"), ("Zaria", "Zaria"),
        ("Kano", "Kano"), ("Wudil", "Wudil"),
        ("Katsina", "Katsina"), ("Funtua", "Funtua"),
        ("Birnin Kebbi", "Birnin Kebbi"),
        ("Lokoja", "Lokoja"), ("Anyigba", "Anyigba"),
        ("Ilorin", "Ilorin"), ("Offa", "Offa"),
        ("Ikeja", "Ikeja"), ("Badagry", "Badagry"), ("Epe", "Epe"), ("Ikorodu", "Ikorodu"), ("Surulere", "Surulere"),
        ("Lafia", "Lafia"), ("Keffi", "Keffi"),
        ("Minna", "Minna"), ("Bida", "Bida"),
        ("Abeokuta", "Abeokuta"), ("Sagamu", "Sagamu"),
        ("Akure", "Akure"), ("Ondo", "Ondo"),
        ("Osogbo", "Osogbo"), ("Ile Ife", "Ile Ife"),
        ("Ibadan", "Ibadan"), ("Ogbomoso", "Ogbomoso"),
        ("Jos", "Jos"),
        ("Port Harcourt", "Port Harcourt"), ("Bonny", "Bonny"),
        ("Sokoto", "Sokoto"),
        ("Jalingo", "Jalingo"),
        ("Damaturu", "Damaturu"), ("Potiskum", "Potiskum"),
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