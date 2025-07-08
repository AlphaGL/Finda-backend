from django.urls import path
from .views import (
    product_list, ProductDetailView, ProductCreateView, ProductUpdateView, ProductDeleteView,
    service_list, ServiceDetailView, ServiceCreateView, ServiceUpdateView, ServiceDeleteView,
    ProductRatingCreateView, ServiceRatingCreateView,HomePageView,
    paystack_callback_view,paystack_listing_payment_view,service_reviews,
    product_reviews,AboutPageView,TermsAndConditionsPageView,PrivacyPolicyPageView,ping_view
)

urlpatterns = [ 
    # Home URL
    path('', HomePageView.as_view(), name='home'),

    # About
    path('about/', AboutPageView.as_view(), name='about'),

    # terms_&_condition
    path('terms&conditions/', TermsAndConditionsPageView.as_view(), name='terms_and_conditions'),

    # privacy_policy
    path('privacy-policy/', PrivacyPolicyPageView.as_view(), name='privacy_policy'),

    # Product URLs
    path('products/', product_list, name='product_list'),
    path('products/<int:pk>/', ProductDetailView.as_view(), name='product_detail'),
    path('products/new/', ProductCreateView.as_view(), name='product_create'),
    path('products/<int:pk>/edit/', ProductUpdateView.as_view(), name='product_update'),
    path('products/<int:pk>/delete/', ProductDeleteView.as_view(), name='product_delete'),
    path('products/<int:pk>/rate/', ProductRatingCreateView.as_view(), name='product_rate'),
    path('product/<int:product_id>/reviews/', product_reviews, name='product_reviews'),

    # Service URLs
    path('services/', service_list, name='service_list'),
    path('services/<int:pk>/', ServiceDetailView.as_view(), name='service_detail'),
    path('services/new/', ServiceCreateView.as_view(), name='service_create'),
    path('services/<int:pk>/edit/', ServiceUpdateView.as_view(), name='service_update'),
    path('services/<int:pk>/delete/', ServiceDeleteView.as_view(), name='service_delete'),
    path('services/<int:pk>/rate/', ServiceRatingCreateView.as_view(), name='service_rate'),

    path('service/<int:service_id>/reviews/', service_reviews, name='service_reviews'),

    path('ping/', ping_view, name='ping'),
    # Paystack URLs
    path('products/<int:product_id>/pay/', paystack_listing_payment_view, name='pay_product_listing'),
    path('services/<int:service_id>/pay/', paystack_listing_payment_view, name='pay_service_listing'),
    path('payment/callback/', paystack_callback_view, name='paystack_callback'),
]