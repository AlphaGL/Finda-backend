from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.utils import perform_login
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        user.email = data.get('email')

        # Avoid setting blank or duplicate phone numbers
        if not user.phone:
            user.phone = f"g_{uuid.uuid4().hex[:13]}"  # total = 2 + 13 = 15


        return user

    def pre_social_login(self, request, sociallogin):
        # If the user is already logged in, do nothing
        if request.user.is_authenticated:
            return

        # Extract the email from the social login account
        email = sociallogin.account.extra_data.get('email')

        if email:
            try:
                user = User.objects.get(email=email)
                # Connect the social account to the existing user
                sociallogin.connect(request, user)
                perform_login(request, user, email_verification='optional')
            except User.DoesNotExist:
                pass  # Let allauth handle signup flow if no user with this email exists