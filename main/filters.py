import django_filters
from .models import LocationCategory


class LocationCategoryFilter(django_filters.FilterSet):
    class Meta:
        model = LocationCategory
        fields = ['category','state', 'city']