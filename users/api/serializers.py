# users/api/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone', 'profile', 'password', 'password2', 
                 'user_type', 'business_name', 'business_description', 'business_image')
        extra_kwargs = {
            'profile': {'required': False},
            'business_name': {'required': False},
            'business_description': {'required': False},
            'business_image': {'required': False}
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        
        # Validate vendor-specific fields
        if attrs.get('user_type') == 'vendor':
            if not attrs.get('business_name'):
                raise serializers.ValidationError({"business_name": "Business name is required for vendors."})
        
        return attrs

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_phone(self, value):
        if value and User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        return value

    def create(self, validated_data):
        validated_data.pop('password2')
        
        # Extract business fields
        business_name = validated_data.pop('business_name', None)
        business_description = validated_data.pop('business_description', None)
        business_image = validated_data.pop('business_image', None)
        
        user = User.objects.create_user(
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone=validated_data['phone'],
            password=validated_data['password'],
            user_type=validated_data.get('user_type', 'customer')
        )
        
        # Handle profile upload if present
        if validated_data.get('profile'):
            user.profile = validated_data['profile']
        
        # Handle vendor-specific fields
        if user.user_type == 'vendor':
            user.business_name = business_name
            user.business_description = business_description
            if business_image:
                user.business_image = business_image
        
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'phone', 'profile', 'date_joined', 
                 'user_type', 'business_name', 'business_description', 'business_image')
        read_only_fields = ('email', 'date_joined', 'user_type')

    def update(self, instance, validated_data):
        # Handle profile image upload with error handling
        if 'profile' in validated_data:
            try:
                instance.profile = validated_data['profile']
            except Exception as e:
                if "File size too large" in str(e):
                    raise serializers.ValidationError({
                        'profile': 'The uploaded file exceeds the maximum allowed size. Please upload a smaller image.'
                    })
                else:
                    raise serializers.ValidationError({
                        'profile': f'An error occurred while uploading the image: {str(e)}'
                    })
        
        # Handle business image upload for vendors
        if 'business_image' in validated_data and instance.is_vendor:
            try:
                instance.business_image = validated_data['business_image']
            except Exception as e:
                if "File size too large" in str(e):
                    raise serializers.ValidationError({
                        'business_image': 'The uploaded file exceeds the maximum allowed size. Please upload a smaller image.'
                    })
                else:
                    raise serializers.ValidationError({
                        'business_image': f'An error occurred while uploading the image: {str(e)}'
                    })
        
        # Update other fields
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.phone = validated_data.get('phone', instance.phone)
        
        # Update vendor-specific fields if user is a vendor
        if instance.is_vendor:
            instance.business_name = validated_data.get('business_name', instance.business_name)
            instance.business_description = validated_data.get('business_description', instance.business_description)
        
        instance.save()
        return instance


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            # Don't reveal if email exists for security, but validate format
            pass
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    password = serializers.CharField(required=True, validators=[validate_password])
    password2 = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password2 = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password": "New password fields didn't match."})
        return attrs