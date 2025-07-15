from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LocationCategoryViewSet,
    ProductsViewSet,
    ServicesViewSet,
    ProductRatingViewSet,
    ServiceRatingViewSet,
    InitiatePaymentAPIView,
    VerifyPaymentAPIView
)

router = DefaultRouter()
router.register(r"categories", LocationCategoryViewSet, basename="categories")
router.register(r"products",   ProductsViewSet,         basename="products")
router.register(r"services",   ServicesViewSet,         basename="services")

product_rating_list   = ProductRatingViewSet.as_view({"get":"list","post":"create"})
product_rating_detail = ProductRatingViewSet.as_view({
    "get":"retrieve","put":"update",
    "patch":"partial_update","delete":"destroy"
})
service_rating_list   = ServiceRatingViewSet.as_view({"get":"list","post":"create"})
service_rating_detail = ServiceRatingViewSet.as_view({
    "get":"retrieve","put":"update",
    "patch":"partial_update","delete":"destroy"
})

urlpatterns = [
    path("", include(router.urls)),

    # nested ratings
    path("products/<int:product_pk>/ratings/",
         product_rating_list,   name="productrating-list"),
    path("products/<int:product_pk>/ratings/<int:pk>/",
         product_rating_detail, name="productrating-detail"),

    path("services/<int:service_pk>/ratings/",
         service_rating_list,   name="servicerating-list"),
    path("services/<int:service_pk>/ratings/<int:pk>/",
         service_rating_detail, name="servicerating-detail"),

    # paystack
    path("payments/initiate/", InitiatePaymentAPIView.as_view(),
         name="api-pay-initiate"),
    path("payments/verify/",   VerifyPaymentAPIView.as_view(),
         name="api-pay-verify"),
]
