# api/views.py
from rest_framework import viewsets, filters, status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db.models import Q, Avg
import requests

from ..models import (
    LocationCategory,
    Products,
    Services,
    ProductRating,
    ServiceRating
)
from .serializers import (
    LocationCategorySerializer,
    ProductsSerializer,
    ServicesSerializer,
    ProductRatingSerializer,
    ServiceRatingSerializer,
    ProductCreateSerializer,
    ServiceCreateSerializer,
    HomePageSerializer,
    StatsSerializer
)
from .permissions import IsOwnerOrReadOnly

# ==== STATS FOR DASHBOARD ====
class StatsAPIView(APIView):
    # permission_classes = [IsAuthenticated]
    permission_classes = [AllowAny]

    def get(self, request):
        user = request.user
        user_products = Products.objects.filter(user=user)
        user_services = Services.objects.filter(user=user)
        
        stats = {
            'total_products': user_products.count(),
            'published_products': user_products.filter(product_status='published').count(),
            'pending_products': user_products.filter(product_status='pending').count(),
            'total_services': user_services.count(),
            'published_services': user_services.filter(service_status='published').count(),
            'pending_services': user_services.filter(service_status='pending').count(),
            'total_product_ratings': ProductRating.objects.filter(product__user=user).count(),
            'total_service_ratings': ServiceRating.objects.filter(service__user=user).count(),
        }
        
        serializer = StatsSerializer(stats)
        return Response(serializer.data)

# ==== HOME PAGE DATA ====
class HomePageAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # Get filter parameters
        query = request.query_params.get("search", "")
        category = request.query_params.get("category", "")
        country = request.query_params.get("country", "")
        state = request.query_params.get("state", "")
        city = request.query_params.get("city", "")
        min_rating = request.query_params.get("rating", "")

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

        # Get filter options
        filter_options = {
            'categories': list(Products.objects.values_list('product_category', flat=True).distinct()),
            'countries': list(Products.objects.values_list('product_country', flat=True).distinct()),
            'states': list(Products.objects.values_list('product_state', flat=True).distinct()),
            'cities': list(Products.objects.values_list('product_city', flat=True).distinct()),
        }

        data = {
            'promoted_products': Products.objects.filter(is_promoted=True, product_status='published'),
            'promoted_services': Services.objects.filter(is_promoted=True, service_status='published'),
            'products': products_query,
            'services': services_query,
            'filter_options': filter_options,
            'applied_filters': {
                'search': query,
                'category': category,
                'country': country,
                'state': state,
                'city': city,
                'rating': min_rating,
            }
        }

        serializer = HomePageSerializer(data)
        return Response(serializer.data)

# ==== CATEGORY ====
class LocationCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LocationCategory.objects.all()
    serializer_class = LocationCategorySerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["category", "state", "city"]

# ==== PRODUCTS ====
class ProductsViewSet(viewsets.ModelViewSet):
    queryset = Products.objects.all().order_by("-is_promoted", "-id")
    permission_classes = [IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        "product_category", "product_country",
        "product_state", "product_city",
        "product_status", "is_promoted", "user"
    ]
    search_fields = ["product_name", "product_description", "product_brand"]
    ordering_fields = ["product_price", "is_promoted", "id"]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProductCreateSerializer
        return ProductsSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == 'list':
            # For list view, only show published items unless user requests their own
            if self.request.query_params.get('my_products') == 'true':
                if self.request.user.is_authenticated:
                    return queryset.filter(user=self.request.user)
                else:
                    return queryset.none()
            return queryset.filter(product_status='published')
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, product_status="pending")

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def promote(self, request, pk=None):
        product = self.get_object()
        if product.user != request.user:
            return Response({'detail': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
        
        product.is_promoted = True
        product.save()
        return Response({'detail': 'Product promoted successfully'})

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_products(self, request):
        products = self.get_queryset().filter(user=request.user)
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)

# ==== SERVICES ====
class ServicesViewSet(viewsets.ModelViewSet):
    queryset = Services.objects.all().order_by("-is_promoted", "-id")
    permission_classes = [IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        "service_category", "service_country",
        "service_state", "service_city",
        "service_status", "is_promoted", "user"
    ]
    search_fields = ["service_name", "service_description", "service_provider_name"]
    ordering_fields = ["is_promoted", "id"]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ServiceCreateSerializer
        return ServicesSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == 'list':
            # For list view, only show published items unless user requests their own
            if self.request.query_params.get('my_services') == 'true':
                if self.request.user.is_authenticated:
                    return queryset.filter(user=self.request.user)
                else:
                    return queryset.none()
            return queryset.filter(service_status='published')
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, service_status="pending")

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def promote(self, request, pk=None):
        service = self.get_object()
        if service.user != request.user:
            return Response({'detail': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
        
        service.is_promoted = True
        service.save()
        return Response({'detail': 'Service promoted successfully'})

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_services(self, request):
        services = self.get_queryset().filter(user=request.user)
        serializer = self.get_serializer(services, many=True)
        return Response(serializer.data)

# ==== PRODUCT RATINGS (nested) ====
class ProductRatingViewSet(viewsets.ModelViewSet):
    serializer_class = ProductRatingSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_queryset(self):
        return ProductRating.objects.filter(product_id=self.kwargs["product_pk"])

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        product = get_object_or_404(Products, pk=self.kwargs["product_pk"])
        # Check if user already rated this product
        existing_rating = ProductRating.objects.filter(
            product=product, 
            user=self.request.user
        ).first()
        
        if existing_rating:
            # Update existing rating
            for attr, value in serializer.validated_data.items():
                setattr(existing_rating, attr, value)
            existing_rating.save()
            return existing_rating
        else:
            # Create new rating
            serializer.save(user=self.request.user, product=product)

# ==== SERVICE RATINGS (nested) ====
class ServiceRatingViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceRatingSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_queryset(self):
        return ServiceRating.objects.filter(service_id=self.kwargs["service_pk"])

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        service = get_object_or_404(Services, pk=self.kwargs["service_pk"])
        # Check if user already rated this service
        existing_rating = ServiceRating.objects.filter(
            service=service, 
            user=self.request.user
        ).first()
        
        if existing_rating:
            # Update existing rating
            for attr, value in serializer.validated_data.items():
                setattr(existing_rating, attr, value)
            existing_rating.save()
            return existing_rating
        else:
            # Create new rating
            serializer.save(user=self.request.user, service=service)

# ==== SEARCH API ====
class SearchAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get('q', '')
        category = request.query_params.get('category', '')
        location = request.query_params.get('location', '')
        
        products = Products.objects.filter(product_status='published')
        services = Services.objects.filter(service_status='published')
        
        if query:
            products = products.filter(
                Q(product_name__icontains=query) |
                Q(product_description__icontains=query) |
                Q(product_brand__icontains=query)
            )
            services = services.filter(
                Q(service_name__icontains=query) |
                Q(service_description__icontains=query) |
                Q(service_provider_name__icontains=query)
            )
        
        if category:
            products = products.filter(product_category=category)
            services = services.filter(service_category=category)
        
        if location:
            products = products.filter(
                Q(product_state__icontains=location) |
                Q(product_city__icontains=location)
            )
            services = services.filter(
                Q(service_state__icontains=location) |
                Q(service_city__icontains=location)
            )
        
        return Response({
            'products': ProductsSerializer(products[:20], many=True).data,
            'services': ServicesSerializer(services[:20], many=True).data,
            'total_results': products.count() + services.count()
        })

# ==== PAYSTACK INITIATE ====
class InitiatePaymentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        item_type = request.data.get("item_type")
        item_id = request.data.get("item_id")
        
        if item_type == "product":
            item = get_object_or_404(Products, pk=item_id, user=request.user)
            if item.is_paid:
                return Response({"detail": "Product is already paid for"}, status=status.HTTP_400_BAD_REQUEST)
        elif item_type == "service":
            item = get_object_or_404(Services, pk=item_id, user=request.user)
            if item.is_paid:
                return Response({"detail": "Service is already paid for"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"detail": "Invalid item_type"}, status=status.HTTP_400_BAD_REQUEST)

        amount = 1000  # Base listing fee
        if getattr(item, "is_promoted", False):
            amount += item.promotion_fee

        payload = {
            "amount": amount * 100,  # Convert to kobo
            "email": request.user.email,
            "callback_url": request.build_absolute_uri("/api/payments/verify/"),
            "metadata": {
                "item_type": item_type,
                "item_id": item_id,
                "user_id": request.user.id
            },
        }
        
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }
        
        response = requests.post(settings.PAYSTACK_PAYMENT_URL, json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()["data"]
            return Response({
                "authorization_url": data["authorization_url"],
                "reference": data["reference"],
                "amount": amount,
            })
        else:
            return Response(response.json(), status=status.HTTP_502_BAD_GATEWAY)

# ==== PAYSTACK VERIFY ====
class VerifyPaymentAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        reference = request.query_params.get("reference")
        if not reference:
            return Response({"detail": "Missing reference"}, status=status.HTTP_400_BAD_REQUEST)

        verify_url = f"https://api.paystack.co/transaction/verify/{reference}"
        headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
        
        response = requests.get(verify_url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()["data"]
            metadata = data.get("metadata", {})
            item_type = metadata.get("item_type")
            item_id = metadata.get("item_id")

            if data.get("status") == "success":
                if item_type == "product":
                    item = get_object_or_404(Products, pk=item_id)
                    item.product_status = "published"
                    item.is_paid = True
                    item.save()
                    return Response({
                        "detail": "Payment verified and product published.",
                        "item_type": "product",
                        "item": ProductsSerializer(item).data
                    })
                elif item_type == "service":
                    item = get_object_or_404(Services, pk=item_id)
                    item.service_status = "published"
                    item.is_paid = True
                    item.save()
                    return Response({
                        "detail": "Payment verified and service published.",
                        "item_type": "service",
                        "item": ServicesSerializer(item).data
                    })
            else:
                return Response({"detail": "Payment not successful."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(response.json(), status=status.HTTP_502_BAD_GATEWAY)

# ==== FILTER OPTIONS ====
class FilterOptionsAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        categories = list(LocationCategory.CATEGORY_CHOICES)
        countries = list(LocationCategory.COUNTRY_CHOICES)
        states = list(LocationCategory.STATE_CHOICES)
        cities = list(LocationCategory.CITY_CHOICES)
        
        return Response({
            'categories': categories,
            'countries': countries,
            'states': states,
            'cities': cities,
        })