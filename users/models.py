from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from cloudinary.models import CloudinaryField
class CustomUserManager(BaseUserManager):
    def create_user(self, email, first_name, last_name, phone, password=None, **extra_fields):
        if not email and not phone:
            raise ValueError("Either Email or Phone number must be set")
        email = self.normalize_email(email) if email else None
        user = self.model(email=email, first_name=first_name, last_name=last_name, phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, first_name, last_name, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(email, first_name, last_name, phone, password, **extra_fields)

class CustomUser(AbstractUser):
    username = None  # Remove username field
    profile = CloudinaryField('users/profile')
    email = models.EmailField(unique=True, default="default@example.com")  # Email can be optional
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    phone = models.CharField(max_length=35, unique=True, null=True, blank=True)

    objects = CustomUserManager()  # Attach custom manager

    USERNAME_FIELD = "email"  # Default login field (overridden by custom backend)
    REQUIRED_FIELDS = ["first_name", "last_name", "phone"]

    def __str__(self):
        return self.email if self.email else self.phone