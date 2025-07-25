# Generated by Django 5.2.4 on 2025-07-24 23:44

import cloudinary.models
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ProductRating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.DecimalField(choices=[(1.0, '1.0'), (1.5, '1.5'), (2.0, '2.0'), (2.5, '2.5'), (3.0, '3.0'), (3.5, '3.5'), (4.0, '4.0'), (4.5, '4.5'), (5.0, '5.0')], decimal_places=1, max_digits=2)),
                ('review_title', models.CharField(blank=True, max_length=200, null=True)),
                ('review', models.TextField(blank=True, max_length=1500, null=True)),
                ('pros', models.TextField(blank=True, max_length=500, null=True)),
                ('cons', models.TextField(blank=True, max_length=500, null=True)),
                ('would_recommend', models.BooleanField(default=True)),
                ('is_active', models.BooleanField(default=True)),
                ('is_verified_purchase', models.BooleanField(default=False)),
                ('helpful_count', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Products',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('product_name', models.CharField(max_length=200)),
                ('slug', models.SlugField(blank=True, max_length=220, unique=True)),
                ('product_description', models.TextField(max_length=3000)),
                ('featured_image', cloudinary.models.CloudinaryField(max_length=255, verbose_name='product_images/featured')),
                ('gallery_images', models.JSONField(blank=True, default=list, help_text='Store multiple Cloudinary URLs')),
                ('product_price', models.DecimalField(decimal_places=2, max_digits=15)),
                ('original_price', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ('currency', models.CharField(default='NGN', max_length=3)),
                ('is_negotiable', models.BooleanField(default=True)),
                ('address_details', models.CharField(blank=True, max_length=200, null=True)),
                ('tags', models.CharField(blank=True, help_text='Comma-separated tags', max_length=500, null=True)),
                ('product_brand', models.CharField(blank=True, max_length=200, null=True)),
                ('product_model', models.CharField(blank=True, max_length=200, null=True)),
                ('product_condition', models.CharField(choices=[('new', 'Brand New'), ('like_new', 'Like New'), ('excellent', 'Excellent'), ('good', 'Good'), ('fair', 'Fair'), ('poor', 'Poor'), ('refurbished', 'Refurbished')], default='new', max_length=20)),
                ('product_status', models.CharField(choices=[('draft', 'Draft'), ('pending', 'Pending Payment'), ('published', 'Published'), ('suspended', 'Suspended'), ('sold', 'Sold'), ('expired', 'Expired')], default='draft', max_length=20)),
                ('provider_phone', models.CharField(max_length=20, validators=[django.core.validators.RegexValidator(message='Phone number must be valid', regex='^\\+?1?\\d{9,15}$')])),
                ('provider_email', models.EmailField(blank=True, max_length=254, null=True)),
                ('provider_whatsapp', models.CharField(blank=True, max_length=20, null=True)),
                ('is_paid', models.BooleanField(default=False)),
                ('is_promoted', models.BooleanField(default=False)),
                ('is_featured', models.BooleanField(default=False)),
                ('promotion_fee', models.DecimalField(decimal_places=2, default=10.0, max_digits=10)),
                ('views_count', models.PositiveIntegerField(default=0)),
                ('favorites_count', models.PositiveIntegerField(default=0)),
                ('meta_title', models.CharField(blank=True, max_length=160, null=True)),
                ('meta_description', models.CharField(blank=True, max_length=320, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name_plural': 'Products',
                'ordering': ['-is_promoted', '-is_featured', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SearchHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('search_term', models.CharField(max_length=200)),
                ('search_type', models.CharField(choices=[('product', 'Product'), ('service', 'Service'), ('both', 'Both')], default='both', max_length=20)),
                ('results_count', models.PositiveIntegerField(default=0)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ServiceRating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.DecimalField(choices=[(1.0, '1.0'), (1.5, '1.5'), (2.0, '2.0'), (2.5, '2.5'), (3.0, '3.0'), (3.5, '3.5'), (4.0, '4.0'), (4.5, '4.5'), (5.0, '5.0')], decimal_places=1, max_digits=2)),
                ('review_title', models.CharField(blank=True, max_length=200, null=True)),
                ('review', models.TextField(blank=True, max_length=1500, null=True)),
                ('communication_rating', models.DecimalField(blank=True, choices=[(1.0, '1.0'), (1.5, '1.5'), (2.0, '2.0'), (2.5, '2.5'), (3.0, '3.0'), (3.5, '3.5'), (4.0, '4.0'), (4.5, '4.5'), (5.0, '5.0')], decimal_places=1, max_digits=2, null=True)),
                ('quality_rating', models.DecimalField(blank=True, choices=[(1.0, '1.0'), (1.5, '1.5'), (2.0, '2.0'), (2.5, '2.5'), (3.0, '3.0'), (3.5, '3.5'), (4.0, '4.0'), (4.5, '4.5'), (5.0, '5.0')], decimal_places=1, max_digits=2, null=True)),
                ('timeliness_rating', models.DecimalField(blank=True, choices=[(1.0, '1.0'), (1.5, '1.5'), (2.0, '2.0'), (2.5, '2.5'), (3.0, '3.0'), (3.5, '3.5'), (4.0, '4.0'), (4.5, '4.5'), (5.0, '5.0')], decimal_places=1, max_digits=2, null=True)),
                ('would_recommend', models.BooleanField(default=True)),
                ('would_hire_again', models.BooleanField(default=True)),
                ('is_active', models.BooleanField(default=True)),
                ('is_verified_customer', models.BooleanField(default=False)),
                ('helpful_count', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Services',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('service_name', models.CharField(max_length=200)),
                ('slug', models.SlugField(blank=True, max_length=220, unique=True)),
                ('service_description', models.TextField(max_length=3000)),
                ('featured_image', cloudinary.models.CloudinaryField(max_length=255, verbose_name='service_images/featured')),
                ('gallery_images', models.JSONField(blank=True, default=list)),
                ('serves_remote', models.BooleanField(default=False, help_text='Can provide service remotely')),
                ('service_radius', models.PositiveIntegerField(blank=True, help_text='Service radius in KM', null=True)),
                ('tags', models.CharField(blank=True, max_length=500, null=True)),
                ('provider_name', models.CharField(max_length=200)),
                ('provider_title', models.CharField(blank=True, max_length=200, null=True)),
                ('provider_bio', models.TextField(blank=True, max_length=1000, null=True)),
                ('provider_expertise', models.TextField(max_length=1000)),
                ('provider_experience', models.CharField(choices=[('beginner', '0-1 years'), ('intermediate', '1-3 years'), ('experienced', '3-5 years'), ('expert', '5-10 years'), ('master', '10+ years')], default='beginner', max_length=20)),
                ('provider_certifications', models.TextField(blank=True, max_length=500, null=True)),
                ('provider_languages', models.CharField(blank=True, max_length=200, null=True)),
                ('provider_email', models.EmailField(max_length=254)),
                ('provider_phone', models.CharField(max_length=20, validators=[django.core.validators.RegexValidator(message='Phone number must be valid', regex='^\\+?1?\\d{9,15}$')])),
                ('provider_whatsapp', models.CharField(blank=True, max_length=20, null=True)),
                ('provider_website', models.URLField(blank=True, null=True)),
                ('provider_linkedin', models.URLField(blank=True, null=True)),
                ('starting_price', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ('max_price', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ('currency', models.CharField(default='NGN', max_length=3)),
                ('price_type', models.CharField(choices=[('fixed', 'Fixed Price'), ('hourly', 'Per Hour'), ('daily', 'Per Day'), ('weekly', 'Per Week'), ('monthly', 'Per Month'), ('project', 'Per Project'), ('negotiable', 'Negotiable')], default='negotiable', max_length=20)),
                ('service_status', models.CharField(choices=[('draft', 'Draft'), ('pending', 'Pending Payment'), ('published', 'Published'), ('suspended', 'Suspended'), ('unavailable', 'Unavailable'), ('expired', 'Expired')], default='draft', max_length=20)),
                ('response_time', models.CharField(blank=True, help_text="e.g., '24 hours', 'Same day'", max_length=50, null=True)),
                ('availability', models.CharField(blank=True, max_length=200, null=True)),
                ('is_paid', models.BooleanField(default=False)),
                ('is_promoted', models.BooleanField(default=False)),
                ('is_featured', models.BooleanField(default=False)),
                ('is_verified', models.BooleanField(default=False)),
                ('promotion_fee', models.DecimalField(decimal_places=2, default=10.0, max_digits=10)),
                ('views_count', models.PositiveIntegerField(default=0)),
                ('contacts_count', models.PositiveIntegerField(default=0)),
                ('meta_title', models.CharField(blank=True, max_length=160, null=True)),
                ('meta_description', models.CharField(blank=True, max_length=320, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name_plural': 'Services',
                'ordering': ['-is_promoted', '-is_featured', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='State',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('code', models.CharField(blank=True, help_text='State/Province code', max_length=10, null=True)),
                ('type', models.CharField(choices=[('state', 'State'), ('province', 'Province'), ('region', 'Region'), ('territory', 'Territory'), ('district', 'District')], default='state', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='UserFavorite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(max_length=120, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('category_type', models.CharField(choices=[('product', 'Product Category'), ('service', 'Service Category'), ('both', 'Both Products & Services')], default='both', max_length=20)),
                ('icon', models.CharField(blank=True, help_text='CSS icon class or emoji', max_length=50, null=True)),
                ('image', cloudinary.models.CloudinaryField(blank=True, max_length=255, null=True, verbose_name='category_images')),
                ('is_featured', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='subcategories', to='main.category')),
            ],
            options={
                'verbose_name_plural': 'Categories',
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='Country',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('code', models.CharField(help_text='ISO country code (e.g., US, NG, GB)', max_length=3, unique=True)),
                ('phone_code', models.CharField(blank=True, help_text='Country calling code (e.g., +1, +234)', max_length=10, null=True)),
                ('currency_code', models.CharField(blank=True, help_text='ISO currency code (e.g., USD, NGN)', max_length=3, null=True)),
                ('currency_symbol', models.CharField(blank=True, help_text='Currency symbol (e.g., $, ₦)', max_length=5, null=True)),
                ('flag_emoji', models.CharField(blank=True, max_length=10, null=True)),
                ('continent', models.CharField(blank=True, max_length=50, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name_plural': 'Countries',
                'ordering': ['sort_order', 'name'],
                'indexes': [models.Index(fields=['code'], name='main_countr_code_a83925_idx'), models.Index(fields=['is_active', 'sort_order'], name='main_countr_is_acti_ef6e8a_idx')],
            },
        ),
        migrations.CreateModel(
            name='City',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('latitude', models.DecimalField(blank=True, decimal_places=8, max_digits=10, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=8, max_digits=11, null=True)),
                ('population', models.PositiveIntegerField(blank=True, null=True)),
                ('timezone', models.CharField(blank=True, max_length=50, null=True)),
                ('is_capital', models.BooleanField(default=False)),
                ('is_major_city', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('country', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cities', to='main.country')),
            ],
            options={
                'verbose_name_plural': 'Cities',
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='LocationCache',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cache_key', models.CharField(max_length=200, unique=True)),
                ('cache_data', models.JSONField()),
                ('expires_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'indexes': [models.Index(fields=['cache_key', 'expires_at'], name='main_locati_cache_k_cf442e_idx')],
            },
        ),
    ]
