# api/urls.py - Enhanced URL Configuration
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    # Location ViewSets
    CountryViewSet,
    StateViewSet,
    CityViewSet,
    CategoryViewSet,
    
    # Core Business ViewSets
    ProductsViewSet,
    ServicesViewSet,
    ProductRatingViewSet,
    ServiceRatingViewSet,
    
    # API Views
    HomePageAPIView,
    StatsAPIView,
    SearchAPIView,
    # FilterOptionsAPIView,
    
    # Location & Utility Views
    LocationHierarchyAPIView,
    LocationCacheAPIView,
    
    # Payment Views
    PaystackInitiatePaymentAPIView,
    PaystackCallbackAPIView,
    PaymentStatusAPIView,
    PaymentHistoryAPIView,
    PromoteItemAPIView,
    PromotionCallbackAPIView,
    
    # Analytics & Reporting Views
    TrendingSearchesAPIView,
    PopularCategoriesAPIView,
    UserDashboardAPIView,
    AdminStatsAPIView,
    ModerationQueueAPIView,
    ReportsAPIView,
    
    # Bulk Operations & Export
    BulkOperationsAPIView,
    ExportDataAPIView,
    
    # Health & System
    HealthCheckAPIView,
    APIVersionAPIView,
)

# Router Configuration
router = DefaultRouter()

# Location endpoints
router.register(r"countries", CountryViewSet, basename="countries")
router.register(r"states", StateViewSet, basename="states")
router.register(r"cities", CityViewSet, basename="cities")
router.register(r"categories", CategoryViewSet, basename="categories")

# Core business endpoints
router.register(r"products", ProductsViewSet, basename="products")
router.register(r"services", ServicesViewSet, basename="services")

# Nested rating views
product_rating_list = ProductRatingViewSet.as_view({"get": "list", "post": "create"})
product_rating_detail = ProductRatingViewSet.as_view({
    "get": "retrieve",
    "put": "update",
    "patch": "partial_update",
    "delete": "destroy"
})

service_rating_list = ServiceRatingViewSet.as_view({"get": "list", "post": "create"})
service_rating_detail = ServiceRatingViewSet.as_view({
    "get": "retrieve",
    "put": "update",
    "patch": "partial_update",
    "delete": "destroy"
})

urlpatterns = [
    # Core router URLs
    path("", include(router.urls)),
    
    # ===========================
    #  HOMEPAGE & CORE FEATURES
    # ===========================
    path("home/", HomePageAPIView.as_view(), name="api-home"),
    path("stats/", StatsAPIView.as_view(), name="api-stats"),
    path("search/", SearchAPIView.as_view(), name="api-search"),
    # path("filter-options/", FilterOptionsAPIView.as_view(), name="api-filter-options"),
    
    # ===========================
    #  LOCATION & HIERARCHY
    # ===========================
    path("location/hierarchy/", LocationHierarchyAPIView.as_view(), name="api-location-hierarchy"),
    path("location/cache/", LocationCacheAPIView.as_view(), name="api-location-cache"),
    
    # ===========================
    #  NESTED PRODUCT RATINGS
    # ===========================
    path(
        "products/<slug:product_slug>/ratings/",
        product_rating_list,
        name="productrating-list"
    ),
    path(
        "products/<slug:product_slug>/ratings/<int:pk>/",
        product_rating_detail,
        name="productrating-detail"
    ),
    
    # ===========================
    #  NESTED SERVICE RATINGS
    # ===========================
    path(
        "services/<slug:service_slug>/ratings/",
        service_rating_list,
        name="servicerating-list"
    ),
    path(
        "services/<slug:service_slug>/ratings/<int:pk>/",
        service_rating_detail,
        name="servicerating-detail"
    ),
    
    # ===========================
    #  PAYMENT ENDPOINTS
    # ===========================
    
    # Paystack Integration
    path(
        "payments/initiate/",
        PaystackInitiatePaymentAPIView.as_view(),
        name="api-payment-initiate"
    ),
    path(
        "payments/verify/",
        PaystackCallbackAPIView.as_view(),
        name="api-payment-verify"
    ),
    path(
        "payments/status/",
        PaymentStatusAPIView.as_view(),
        name="api-payment-status"
    ),
    path(
        "payments/history/",
        PaymentHistoryAPIView.as_view(),
        name="api-payment-history"
    ),
    
    # Promotion Payments
    path(
        "payments/promote/",
        PromoteItemAPIView.as_view(),
        name="api-promote-item"
    ),
    path(
        "payments/promotion-callback/",
        PromotionCallbackAPIView.as_view(),
        name="api-promotion-callback"
    ),
    
    # Payment Callbacks (webhooks)
    path(
        "payment/paystack/callback/",
        PaystackCallbackAPIView.as_view(),
        name="paystack-callback"
    ),
    path(
        "payment/paystack/promotion-callback/",
        PromotionCallbackAPIView.as_view(),
        name="paystack-promotion-callback"
    ),
    
    # ===========================
    #  ANALYTICS & TRENDING
    # ===========================
    path(
        "analytics/trending-searches/",
        TrendingSearchesAPIView.as_view(),
        name="api-trending-searches"
    ),
    path(
        "analytics/popular-categories/",
        PopularCategoriesAPIView.as_view(),
        name="api-popular-categories"
    ),
    
    # ===========================
    #  USER DASHBOARD
    # ===========================
    path(
        "dashboard/",
        UserDashboardAPIView.as_view(),
        name="api-user-dashboard"
    ),
    
    # ===========================
    #  ADMIN & MODERATION
    # ===========================
    path(
        "admin/stats/",
        AdminStatsAPIView.as_view(),
        name="api-admin-stats"
    ),
    path(
        "admin/moderation/",
        ModerationQueueAPIView.as_view(),
        name="api-moderation-queue"
    ),
    path(
        "admin/reports/",
        ReportsAPIView.as_view(),
        name="api-reports"
    ),
    
    # ===========================
    #  BULK OPERATIONS
    # ===========================
    path(
        "bulk/operations/",
        BulkOperationsAPIView.as_view(),
        name="api-bulk-operations"
    ),
    
    # ===========================
    #  DATA EXPORT
    # ===========================
    path(
        "export/data/",
        ExportDataAPIView.as_view(),
        name="api-export-data"
    ),
    
    # ===========================
    #  SYSTEM HEALTH & INFO
    # ===========================
    path(
        "health/",
        HealthCheckAPIView.as_view(),
        name="api-health-check"
    ),
    path(
        "version/",
        APIVersionAPIView.as_view(),
        name="api-version"
    ),
]