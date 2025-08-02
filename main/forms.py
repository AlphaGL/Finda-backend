from django import forms
from .models import Products, ProductRating, Services, ServiceRating

class ProductForm(forms.ModelForm):
    class Meta:
        model = Products
        exclude = ['product_status', 'is_paid', 'user', 'promotion_fee', 'slug', 'views_count', 'favorites_count', 'created_at', 'updated_at', 'published_at']
        widgets = {
            "product_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter product name"}),
            "featured_image": forms.ClearableFileInput(attrs={"class": "form-control-file"}),
            "product_description": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Enter product description"}),
            "product_price": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Enter product price"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "country": forms.Select(attrs={"class": "form-control"}),
            "state": forms.Select(attrs={"class": "form-control"}),
            "city": forms.Select(attrs={"class": "form-control"}),
            "product_brand": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter product brand"}),
            "product_model": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter product model"}),
            "product_condition": forms.Select(attrs={"class": "form-control"}),
            "provider_phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter provider phone number"}),
            "provider_email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Enter provider email"}),
            "provider_whatsapp": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter WhatsApp number"}),
            "address_details": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter address details"}),
            "tags": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter tags separated by commas"}),
            "currency": forms.Select(attrs={"class": "form-control"}),
            "original_price": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Enter original price (optional)"}),
            "is_negotiable": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "meta_title": forms.TextInput(attrs={"class": "form-control", "placeholder": "SEO Title (optional)"}),
            "meta_description": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "SEO Description (optional)"}),
        }
    
    is_promoted = forms.BooleanField(required=False, label="Promote this product", widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

class ProductRatingForm(forms.ModelForm):
    class Meta:
        model = ProductRating
        fields = ["rating", "review_title", "review", "pros", "cons", "would_recommend"]
        widgets = {
            "rating": forms.Select(attrs={"class": "form-select form-select-lg"}),
            "review_title": forms.TextInput(attrs={"class": "form-control form-control-lg", "placeholder": "Review Title (optional)"}),
            "review": forms.Textarea(attrs={"class": "form-control form-control-lg", "rows": 3, "placeholder": "Write your review (optional)"}),
            "pros": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "What did you like? (optional)"}),
            "cons": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "What could be improved? (optional)"}),
            "would_recommend": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Services
        exclude = ['service_status', 'is_paid', 'user', 'promotion_fee', 'slug', 'views_count', 'contacts_count', 'created_at', 'updated_at', 'published_at']
        widgets = {
            "service_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter service name"}),
            "featured_image": forms.ClearableFileInput(attrs={"class": "form-control-file"}),
            "service_description": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Enter service description"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "country": forms.Select(attrs={"class": "form-control"}),
            "state": forms.Select(attrs={"class": "form-control"}),
            "city": forms.Select(attrs={"class": "form-control"}),
            "provider_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter provider name"}),
            "provider_title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter provider title"}),
            "provider_bio": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Enter provider bio"}),
            "provider_expertise": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Enter provider expertise"}),
            "provider_experience": forms.Select(attrs={"class": "form-control"}),
            "provider_certifications": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Enter certifications"}),
            "provider_languages": forms.TextInput(attrs={"class": "form-control", "placeholder": "Languages spoken"}),
            "provider_email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Enter provider email"}),
            "provider_phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter provider phone number"}),
            "provider_whatsapp": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter WhatsApp number"}),
            "provider_website": forms.URLInput(attrs={"class": "form-control", "placeholder": "Website URL (optional)"}),
            "provider_linkedin": forms.URLInput(attrs={"class": "form-control", "placeholder": "LinkedIn URL (optional)"}),
            "starting_price": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Starting price"}),
            "max_price": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Maximum price"}),
            "currency": forms.Select(attrs={"class": "form-control"}),
            "price_type": forms.Select(attrs={"class": "form-control"}),
            "response_time": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., '24 hours'"}),
            "availability": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., 'Mon-Fri 9-5'"}),
            "serves_remote": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "service_radius": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Service radius in KM"}),
            "tags": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter tags separated by commas"}),
            "meta_title": forms.TextInput(attrs={"class": "form-control", "placeholder": "SEO Title (optional)"}),
            "meta_description": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "SEO Description (optional)"}),
        }

    is_promoted = forms.BooleanField(required=False, label="Promote this Service", widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

class ServiceRatingForm(forms.ModelForm):
    class Meta:
        model = ServiceRating
        fields = ["rating", "review_title", "review", "communication_rating", "quality_rating", "timeliness_rating", "would_recommend", "would_hire_again"]
        widgets = {
            "rating": forms.Select(attrs={"class": "form-control"}),
            "review_title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Review Title (optional)"}),
            "review": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Write your review (optional)"}),
            "communication_rating": forms.Select(attrs={"class": "form-control"}),
            "quality_rating": forms.Select(attrs={"class": "form-control"}),
            "timeliness_rating": forms.Select(attrs={"class": "form-control"}),
            "would_recommend": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "would_hire_again": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }