from django.urls import reverse_lazy,reverse
from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView,TemplateView
from django.db.models import Q
from .models import Products, Services, ProductRating, ServiceRating, LocationCategory
from django.db.models import Avg
from .filters import LocationCategoryFilter
from django.contrib import messages
from .forms import *
from django.core.exceptions import PermissionDenied
from cloudinary.exceptions import Error as CloudinaryError

from django.contrib.auth.decorators import login_required

# paystack pay before listing imports

from django.shortcuts import render, redirect
from django.contrib import messages
import requests
from django.views.decorators.http import require_GET
from django.conf import settings
from django.views import View
import logging
from django.http import JsonResponse


# ===========================
# HOME PAGE
# ===========================

def ping_view(request):
    return JsonResponse({"status": "OK"})


class HomePageView(TemplateView):
    template_name = "main/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter parameters from GET request
        query = self.request.GET.get("search", "")
        category = self.request.GET.get("category", "")
        country = self.request.GET.get("country", "")
        state = self.request.GET.get("state", "")
        city = self.request.GET.get("city", "")
        min_rating = self.request.GET.get("rating", "")

        # Products filtering
        products_query = Products.objects.filter(product_status='published')
        if query:
            products_query = products_query.filter(Q(product_name__icontains=query))
        if category:
            products_query = products_query.filter(product_category__iexact=category)
        if country:
            products_query = products_query.filter(product_country__iexact=country)
        if state:
            products_query = products_query.filter(product_state__iexact=state)
        if city:
            products_query = products_query.filter(product_city__iexact=city)
        if min_rating:
            products_query = products_query.annotate(avg_rating=Avg("product_ratings__rating")).filter(avg_rating__gte=float(min_rating))

        # Services filtering
        services_query = Services.objects.filter(service_status='published')
        if query:
            services_query = services_query.filter(Q(service_name__icontains=query))
        if category:
            services_query = services_query.filter(service_category__iexact=category)
        if country:
            services_query = services_query.filter(service_country__iexact=country)
        if state:
            services_query = services_query.filter(service_state__iexact=state)
        if city:
            services_query = services_query.filter(service_city__iexact=city)
        if min_rating:
            services_query = services_query.annotate(avg_rating=Avg("service_ratings__rating")).filter(avg_rating__gte=float(min_rating))

        # Get categories, countries, states, and cities
        product_categories = Products.objects.values_list('product_category', flat=True).distinct()
        service_categories = Services.objects.values_list('service_category', flat=True).distinct()
        countries = Products.objects.values_list('product_country', flat=True).distinct()  # Assuming the same countries for both products and services
        states = Products.objects.values_list('product_state', flat=True).distinct()  # Assuming the same states for both products and services
        cities = Products.objects.values_list('product_city', flat=True).distinct()  # Assuming the same cities for both products and services

        # Add promoted items to the context
        context.update({
            "promoted_products": Products.objects.filter(is_promoted=True, product_status='published'),
            "promoted_services": Services.objects.filter(is_promoted=True, service_status='published'),
            "products": products_query,
            "services": services_query,
            "product_categories": product_categories,
            "service_categories": service_categories,
            "countries": countries,
            "states": states,
            "cities": cities,
            "selected_category": category,
            "selected_country": country,
            "selected_state": state,
            "selected_city": city,
            "selected_rating": min_rating,
        })
        
        return context

# ===========================
# ABOUT PAGE
# ===========================
class AboutPageView(TemplateView):
    template_name = "main/about.html"


# ===========================
# TERMS AND CONDITIONS
# ===========================
class TermsAndConditionsPageView(TemplateView):
    template_name = "main/terms_&_conditions.html"


# ===========================
# PRIVACY POLICY
# ===========================
class PrivacyPolicyPageView(TemplateView):
    template_name = "main/privacy_policy.html"


# ====================================
#  PRODUCT VIEWS WITH SEARCH & FILTER
# ====================================


def product_list(request):
    queryset = Products.objects.filter(product_status='published').order_by('-is_promoted', '-id')  # Order by 'is_promoted' and then by id


    # Filter parameters
    query = request.GET.get("search", "")
    category = request.GET.get("category", "")
    country = request.GET.get("country", "")
    state = request.GET.get("state", "")
    city = request.GET.get("city", "")
    min_rating = request.GET.get("rating", "")

    # Apply filters
    if query:
        queryset = queryset.filter(Q(product_name__icontains=query))
    if category:
        queryset = queryset.filter(product_category__iexact=category)

    if country:
        queryset = queryset.filter(product_country__iexact=country)

    if state:
        queryset = queryset.filter(product_state__iexact=state)

    if city:
        queryset = queryset.filter(product_city__iexact=city)

    if min_rating:
        queryset = queryset.annotate(avg_rating=Avg("product_ratings__rating")).filter(avg_rating__gte=float(min_rating))

    categories = Products.objects.values_list('product_category', flat=True).distinct()
    countries = Products.objects.values_list('product_country', flat=True).distinct()
    states = Products.objects.values_list('product_state', flat=True).distinct()
    cities = Products.objects.values_list('product_city', flat=True).distinct()

    context = {
        "products": queryset,
        "categories": categories,
        "countries": countries,
        "states": states,
        "cities": cities,
        "selected_category": category,
        "selected_country": country,
        "selected_state": state,
        "selected_city": city,
        "selected_rating": min_rating,
    }

    return render(request, "main/products_list.html", context)


class ProductDetailView(DetailView):
    model = Products
    template_name = "main/product_details.html"
    context_object_name = "product"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ratings'] = self.object.product_ratings.all()
        context['average_rating'] = self.object.average_rating()
        context['rating_count'] = self.object.rating_count()
        return context

class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Products
    context_object_name = 'product'
    template_name = "main/product_form.html"
    form_class = ProductForm
    success_url = reverse_lazy("user_dashboard")

    def form_valid(self, form):
        form.instance.user = self.request.user
        product = form.save(commit=False)  # Prevent immediate save
        product.product_status = 'pending'  # Ensure status is set explicitly
        
        try:
            product.save()  # Save the product
            return redirect('pay_product_listing', product_id=product.id)
        except CloudinaryError as e:  # Catch the Cloudinary file size error
            form.add_error(None, f"File size too large. Maximum allowed size is 10MB. {str(e)}")
            return self.form_invalid(form)
        except Exception as e:
            form.add_error(None, f"An error occurred: {str(e)}")  # Add generic error
            return self.form_invalid(form)

class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Products
    context_object_name = 'product'
    template_name = "main/product_form.html"
    fields = ('product_name', 'product_image', 'product_description', 'product_price', 'product_category', 'product_state', 'product_city', 'product_brand', 'product_provider_phone')
    success_url = reverse_lazy("user_dashboard")

    def get_queryset(self):
        """
        Ensure that the user can only edit their own products.
        """
        return Products.objects.filter(user=self.request.user)

    def get_object(self, queryset=None):
        """
        Get the product object to be edited by the user.
        """
        product = super().get_object(queryset)
        # Ensure the user can only edit their own products
        if product.user != self.request.user:
            raise PermissionDenied("You do not have permission to edit this product.")
        return product

    def form_valid(self, form):
        product = form.save(commit=False)
        
        try:
            product.save()  # Save the product
            return redirect('user_dashboard')
        except CloudinaryError as e:  # Catch the Cloudinary file size error
            form.add_error(None, f"File size too large. Maximum allowed size is 10MB. {str(e)}")
            return self.form_invalid(form)
        except Exception as e:
            form.add_error(None, f"An error occurred: {str(e)}")
            return self.form_invalid(form)

class ProductDeleteView(LoginRequiredMixin, DeleteView):
    model = Products
    template_name = "main/product_delete.html"
    success_url = reverse_lazy("user_dashboard")

    def get_queryset(self):
        """
        Ensure that the user can only delete their own products.
        """
        return Products.objects.filter(user=self.request.user)

    def get_object(self, queryset=None):
        """
        Get the product object to be deleted by the user.
        """
        product = super().get_object(queryset)
        # Ensure the user can only delete their own products
        if product.user != self.request.user:
            raise PermissionDenied("You do not have permission to delete this product.")
        return product


def service_list(request):
    queryset = Services.objects.filter(service_status='published').order_by('-is_promoted', '-id')  # Order by 'is_promoted' and then by id

    # Filter parameters
    query = request.GET.get("search", "")
    category = request.GET.get("category", "")
    country = request.GET.get("country", "")
    state = request.GET.get("state", "")
    city = request.GET.get("city", "")
    min_rating = request.GET.get("rating", "")

    # Apply filters
    if query:
        queryset = queryset.filter(Q(service_name__icontains=query))

    if category:
        queryset = queryset.filter(service_category__iexact=category)

    if country:
        queryset = queryset.filter(service_country__iexact=country)

    if state:
        queryset = queryset.filter(service_state__iexact=state)

    if city:
        queryset = queryset.filter(service_city__iexact=city)

    if min_rating:
        queryset = queryset.annotate(avg_rating=Avg("service_ratings__rating")).filter(avg_rating__gte=float(min_rating))

    categories = Services.objects.values_list('service_category', flat=True).distinct()
    countries = Services.objects.values_list('service_country', flat=True).distinct()
    states = Services.objects.values_list('service_state', flat=True).distinct()
    cities = Services.objects.values_list('service_city', flat=True).distinct()

    context = {
        "services": queryset,
        "categories": categories,
        "countries": countries,
        "states": states,
        "cities": cities,
        "selected_category": category,
        "selected_country": country,
        "selected_state": state,
        "selected_city": city,
        "selected_rating": min_rating,
    }

    return render(request, "main/services_list.html", context)


class ServiceDetailView(DetailView):
    model = Services
    template_name = "main/service_details.html"
    context_object_name = "service"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ratings'] = self.object.service_ratings.all()
        context['average_rating'] = self.object.average_rating()
        context['rating_count'] = self.object.rating_count()
        return context


class ServiceCreateView(LoginRequiredMixin, CreateView):
    model = Services
    context_object_name = 'service'
    template_name = "main/service_form.html"
    form_class = ServiceForm
    success_url = reverse_lazy("user_dashboard")

    def form_valid(self, form):
        form.instance.user = self.request.user

        service = form.save(commit=False)  # Prevent immediate save
        service.service_status = 'pending'  # Ensure status is set explicitly

        try:
            service.save()  # Save the service
            return redirect('pay_service_listing', service_id=service.id)
        except CloudinaryError as e:  # Catch the Cloudinary file size error
            form.add_error(None, f"File size too large. Maximum allowed size is 10MB. {str(e)}")
            return self.form_invalid(form)
        except Exception as e:
            form.add_error(None, f"An error occurred: {str(e)}")
            return self.form_invalid(form)

class ServiceUpdateView(LoginRequiredMixin, UpdateView):
    model = Services
    context_object_name = 'service'
    template_name = "main/service_form.html"
    fields = (
        'service_name', 'service_image', 'service_description', 'service_category',
        'service_country', 'service_state', 'service_city', 'service_provider_name',
        'service_provider_expertise', 'service_provider_experience_year', 'service_provider_email',
        'service_provider_phone', 'service_status', 'other_service_a', 'other_service_b', 'other_service_c'
    )
    success_url = reverse_lazy("user_dashboard")

    def get_queryset(self):
        """
        Ensure that the user can only edit their own services.
        """
        return Services.objects.filter(user=self.request.user)

    def get_object(self, queryset=None):
        """
        Get the service object to be edited by the user.
        """
        service = super().get_object(queryset)
        # Ensure the user can only edit their own services
        if service.user != self.request.user:
            raise PermissionDenied("You do not have permission to edit this service.")
        return service

    def form_valid(self, form):
        service = form.save(commit=False)
        
        try:
            service.save()  # Save the service
            return redirect('user_dashboard')
        except CloudinaryError as e:  # Catch the Cloudinary file size error
            form.add_error(None, f"File size too large. Maximum allowed size is 10MB. {str(e)}")
            return self.form_invalid(form)
        except Exception as e:
            form.add_error(None, f"An error occurred: {str(e)}")
            return self.form_invalid(form)

class ServiceDeleteView(LoginRequiredMixin, DeleteView):
    model = Services
    template_name = "main/service_delete.html"
    success_url = reverse_lazy("user_dashboard")

    def get_queryset(self):
        """
        Ensure that the user can only delete their own services.
        """
        return Services.objects.filter(user=self.request.user)

    def get_object(self, queryset=None):
        """
        Get the service object to be deleted by the user.
        """
        service = super().get_object(queryset)
        # Ensure the user can only delete their own services
        if service.user != self.request.user:
            raise PermissionDenied("You do not have permission to delete this service.")
        return service
    
    
# ===========================
#  PRODUCT RATING VIEW
# ===========================

class ProductRatingCreateView(LoginRequiredMixin, CreateView):
    model = ProductRating
    template_name = "main/product_rating_form.html"
    fields = ['user_name','rating', 'review',]  # Include user_name in the form fields

    def form_valid(self, form):
        product_id = self.kwargs['pk']  # Get product ID from URL
        product = Products.objects.get(pk=product_id)  # Fetch product from DB
        user = self.request.user

        # Check if user already rated this product
        existing_rating = ProductRating.objects.filter(product=product, user=user).first()
        if existing_rating:
            existing_rating.rating = form.cleaned_data['rating']
            existing_rating.review = form.cleaned_data['review']
            existing_rating.user_name = form.cleaned_data['user_name']  # Save the user_name
            existing_rating.save()
            messages.success(self.request, "Your rating has been updated.")
        else:
            form.instance.user = user
            form.instance.product = product  # Assign product to the rating
            form.instance.user_name = form.cleaned_data['user_name']  # Assign user_name from form input
            form.save()
            messages.success(self.request, "Your rating has been submitted.")

        return redirect(reverse('product_detail', kwargs={'pk': product_id}))

# ===========================
#  SERVICE RATING VIEW
# ===========================
class ServiceRatingCreateView(LoginRequiredMixin, CreateView):
    model = ServiceRating
    template_name = "main/service_rating_form.html"
    fields = ['user_name', 'rating', 'review']  # Now including 'user_name'

    def form_valid(self, form):
        service_id = self.kwargs['pk']  # Get service ID from URL
        service = Services.objects.get(pk=service_id)  # Fetch service from DB
        user = self.request.user

        # Check if user already rated this service
        existing_rating = ServiceRating.objects.filter(service=service, user=user).first()
        if existing_rating:
            existing_rating.rating = form.cleaned_data['rating']
            existing_rating.review = form.cleaned_data['review']
            existing_rating.user_name = form.cleaned_data['user_name']  # Save user_name
            existing_rating.save()
            messages.success(self.request, "Your rating has been updated.")
        else:
            form.instance.user = user
            form.instance.service = service  # Assign service to the rating
            form.save()
            messages.success(self.request, "Your rating has been submitted.")

        return redirect(reverse('service_detail', kwargs={'pk': service_id}))



# ===========================
#  SERVICE REVIEW VIEW
# ===========================

def service_reviews(request, service_id):
    # Get the service by ID
    service = get_object_or_404(Services, id=service_id)
    
    # Fetch the reviews for the service
    reviews = ServiceRating.objects.filter(service=service).order_by('-created_at')
    
    return render(request, 'main/service_review.html', {
        'service': service,
        'reviews': reviews,
    })


# ===========================
#  PRODUCT REVIEW VIEW
# ===========================

def product_reviews(request, product_id):
    # Get the service by ID
    product = get_object_or_404(Products, id=product_id)
    
    # Fetch the reviews for the service
    reviews = ProductRating.objects.filter(product=product).order_by('-created_at')
    
    return render(request, 'main/service_review.html', {
        'service': product,
        'reviews': reviews,
    })

# ===========================
#  PAYSTACK VIEW
# ===========================

def paystack_listing_payment_view(request, product_id=None, service_id=None):
    base_listing_fee = 1000  # Base fee

    item_name = ""
    order_id = None
    total_fee = base_listing_fee

    if product_id:
        item = get_object_or_404(Products, id=product_id)
        item_name = "Product Listing Fee"
        order_id = product_id
        if item.is_promoted:
            total_fee += item.promotion_fee
    elif service_id:
        item = get_object_or_404(Services, id=service_id)
        item_name = "Service Listing Fee"
        order_id = service_id
        if item.is_promoted:
            total_fee += item.promotion_fee
    else:
        messages.error(request, "Invalid request: No product or service ID found.")
        return redirect('home')

    email = request.user.email

    headers = {
        'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
        'Content-Type': 'application/json',
    }

    data = {
        'amount': total_fee * 100,  # Convert to Kobo
        'email': email,
        'callback_url': request.build_absolute_uri('/payment/callback/'),
        'metadata': {
            'order_id': order_id,
            'item_type': 'product' if product_id else 'service',
        },
    }

    response = requests.post(settings.PAYSTACK_PAYMENT_URL, json=data, headers=headers)

    if response.status_code == 200:
        auth_url = response.json()['data']['authorization_url']
        return redirect(auth_url)
    else:
        messages.error(request, "Payment initialization failed.")
        return redirect('home')

@require_GET
def paystack_callback_view(request):
    reference = request.GET.get('reference')

    if not reference:
        messages.error(request, "No payment reference provided.")
        return redirect('home')

    headers = {
        'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
    }

    verify_url = f'https://api.paystack.co/transaction/verify/{reference}'
    response = requests.get(verify_url, headers=headers)

    if response.status_code == 200:
        data = response.json().get('data')
        status = data.get('status')
        metadata = data.get('metadata', {})

        order_id = metadata.get('order_id')
        item_type = metadata.get('item_type')

        if status == 'success':
            if item_type == 'product':
                product = get_object_or_404(Products, id=order_id)
                product.product_status = 'published'
                product.is_paid = True
                product.save()
                messages.success(request, "Product payment successful. Your product is now listed.")
            elif item_type == 'service':
                service = get_object_or_404(Services, id=order_id)
                service.service_status = 'published'
                service.is_paid = True
                service.save()
                messages.success(request, "Service payment successful. Your service is now listed.")
        else:
            messages.error(request, "Payment verification failed or was not successful.")
    else:
        messages.error(request, "Unable to verify payment at this time.")

    return redirect('home')