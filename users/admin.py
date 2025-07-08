from django.contrib import admin
from .models import CustomUser  # Import your actual model, not the manager

admin.site.register(CustomUser)  # Register the model, not the manager