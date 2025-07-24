from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth import get_user_model

class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'placeholder': 'First name'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'placeholder': 'Last name'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'placeholder': 'Enter email'}))
    phone = forms.CharField(max_length=15, required=True, widget=forms.TextInput(attrs={'placeholder': 'Phone (digits only)'}))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Confirm password'}))
    user_type = forms.ChoiceField(
        choices=CustomUser.USER_TYPE_CHOICES, 
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Vendor-specific fields
    business_name = forms.CharField(
        max_length=255, 
        required=False, 
        widget=forms.TextInput(attrs={'placeholder': 'Enter your business name'})
    )
    business_description = forms.CharField(
        required=False, 
        widget=forms.Textarea(attrs={'placeholder': 'Describe your business', 'rows': 4})
    )
    business_image = forms.ImageField(required=False)

    class Meta:
        model = CustomUser
        fields = ['email', 'password1', 'password2', 'first_name', 'last_name', 'phone', 
                 'user_type', 'business_name', 'business_description', 'business_image']

    def clean(self):
        cleaned_data = super().clean()
        user_type = cleaned_data.get('user_type')
        business_name = cleaned_data.get('business_name')
        
        # Validate vendor-specific fields
        if user_type == 'vendor' and not business_name:
            raise forms.ValidationError("Business name is required for vendors.")
        
        return cleaned_data
    
class CustomPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        active_users = CustomUser.objects.filter(email__iexact=email, is_active=True)
        return (u for u in active_users if u.has_usable_password())