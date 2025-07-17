# api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    LocationCategoryViewSet,
    ProductsViewSet,
    ServicesViewSet,
    ProductRatingViewSet,
    ServiceRatingViewSet,
    HomePageAPIView,
    StatsAPIView,
    SearchAPIView,
    FilterOptionsAPIView,
    InitiatePaymentAPIView,
    VerifyPaymentAPIView,
)

router = DefaultRouter()
router.register(r"categories", LocationCategoryViewSet, basename="categories")
router.register(r"products",   ProductsViewSet,         basename="products")
router.register(r"services",   ServicesViewSet,         basename="services")

# Nested rating views
product_rating_list   = ProductRatingViewSet.as_view({"get": "list",   "post": "create"})
product_rating_detail = ProductRatingViewSet.as_view({
    "get":    "retrieve",
    "put":    "update",
    "patch":  "partial_update",
    "delete": "destroy"
})
service_rating_list   = ServiceRatingViewSet.as_view({"get": "list",   "post": "create"})
service_rating_detail = ServiceRatingViewSet.as_view({
    "get":    "retrieve",
    "put":    "update",
    "patch":  "partial_update",
    "delete": "destroy"
})

urlpatterns = [
    # Core resources
    path("", include(router.urls)),

    # Home page & dashboard stats
    path("home/",          HomePageAPIView.as_view(),        name="api-home"),
    path("stats/",         StatsAPIView.as_view(),           name="api-stats"),

    # Search & filters
    path("search/",        SearchAPIView.as_view(),          name="api-search"),
    path("filter-options/", FilterOptionsAPIView.as_view(),  name="api-filter-options"),

    # Nested product ratings
    path(
        "products/<int:product_pk>/ratings/",
        product_rating_list,
        name="productrating-list"
    ),
    path(
        "products/<int:product_pk>/ratings/<int:pk>/",
        product_rating_detail,
        name="productrating-detail"
    ),

    # Nested service ratings
    path(
        "services/<int:service_pk>/ratings/",
        service_rating_list,
        name="servicerating-list"
    ),
    path(
        "services/<int:service_pk>/ratings/<int:pk>/",
        service_rating_detail,
        name="servicerating-detail"
    ),

    # Paystack payments
    path(
        "payments/initiate/",
        InitiatePaymentAPIView.as_view(),
        name="api-pay-initiate"
    ),
    path(
        "payments/verify/",
        VerifyPaymentAPIView.as_view(),
        name="api-pay-verify"
    ),
]
