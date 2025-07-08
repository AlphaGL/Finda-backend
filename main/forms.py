from django import forms
from .models import Products, ProductRating, Services, ServiceRating

class ProductForm(forms.ModelForm):
    class Meta:
        model = Products
        exclude = ['product_status','is_paid', 'user','promotion_fee']
        widgets = {
            "product_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter product name"}),
            "product_image": forms.ClearableFileInput(attrs={"class": "form-control-file"}),
            "product_description": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Enter product description"}),
            "product_price": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Enter product price"}),
            "product_category": forms.Select(attrs={"class": "form-control"}),
            "product_country": forms.Select(attrs={"class": "form-control"}),
            "product_state": forms.Select(attrs={"class": "form-control"}),
            "product_city": forms.Select(attrs={"class": "form-control"}),
            "product_brand": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter product brand"}),
            # "product_provider_email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Enter provider email"}),
            "product_provider_phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter provider phone number"}),
        }
    is_promoted = forms.BooleanField(required=False, label="Promote this product", widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

class ProductRatingForm(forms.ModelForm):
    class Meta:
        model = ProductRating
        fields = ["user_name", "rating", "review",]  # Include user_name as an input field
        widgets = {
            "rating": forms.Select(attrs={"class": "form-select form-select-lg"}),
            "review": forms.Textarea(attrs={"class": "form-control form-control-lg", "rows": 3, "placeholder": "Write your review (optional)"}),
            "Name": forms.TextInput(attrs={"class": "form-control form-control-lg", "placeholder": "Your Name", "required": "true"}),
        }


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Services
        exclude = ['service_status','is_paid', 'user','promotion_fee']
        widgets = {
            "service_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter service name"}),
            "service_image": forms.ClearableFileInput(attrs={"class": "form-control-file"}),
            "service_description": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Enter service description"}),
            "service_category": forms.Select(attrs={"class": "form-control"}),
            "service_country": forms.Select(attrs={"class": "form-control"}),
            "service_state": forms.Select(attrs={"class": "form-control"}),
            "service_city": forms.Select(attrs={"class": "form-control"}),
            "service_provider_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter provider name"}),
            "service_provider_expertise": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Enter provider expertise"}),
            "service_provider_experience_year": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Enter years of experience"}),
            "service_provider_email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Enter provider email"}),
            "service_provider_phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter provider phone number"}),
            "other_service_a": forms.TextInput(attrs={"class": "form-control", "placeholder": "Other service (optional)"}),
            "other_service_b": forms.TextInput(attrs={"class": "form-control", "placeholder": "Other service (optional)"}),
            "other_service_c": forms.TextInput(attrs={"class": "form-control", "placeholder": "Other service (optional)"}),
            "other_service_d": forms.TextInput(attrs={"class": "form-control", "placeholder": "Other service (optional)"}),
            "other_service_e": forms.TextInput(attrs={"class": "form-control", "placeholder": "Other service (optional)"}),
        }

    is_promoted = forms.BooleanField(required=False, label="Promote this Service", widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

class ServiceRatingForm(forms.ModelForm):
    class Meta:
        model = ServiceRating
        fields = ["rating", "review", "user_name"]
        widgets = {
            "rating": forms.Select(attrs={"class": "form-control"}),
            "user_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter your name"}),
            "review": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Write your review (optional)"}),
        }

        