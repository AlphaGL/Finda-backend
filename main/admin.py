from django.contrib import admin
from .models import *

admin.site.register(LocationCategory)
admin.site.register(Products)
admin.site.register(Services)
admin.site.register(ProductRating)
admin.site.register(ServiceRating)