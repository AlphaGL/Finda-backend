# Fixed imports at the top of views.py
from rest_framework import viewsets, filters, status, generics
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db.models import Q, Avg, Count, Sum
from main.location_utils import LocationUtils
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
import requests
from main.filters import CountryFilter,StateFilter,CityFilter,CategoryFilter,ProductsFilter,ServicesFilter,ProductRatingFilter,ServiceRatingFilter
from .permissions import IsAdminOrReadOnly,IsOwnerOrReadOnly
from ..models import (
    Country, State, City, Category,
    Products, Services,
    ProductRating, ServiceRating,
    UserFavorite, SearchHistory,
    LocationCache  # Add this missing import
)

# Add these missing serializer imports (you'll need to create them)
from .serializers import (
    CountrySerializer, StateSerializer, CitySerializer, CategorySerializer,
    ProductsSerializer, ServicesSerializer,
    ProductRatingSerializer, ServiceRatingSerializer,
    ProductCreateSerializer, ServiceCreateSerializer,
    HomePageSerializer, StatsSerializer, SearchSerializer,
    LocationHierarchySerializer, UserFavoriteSerializer,
    PaymentInitiateSerializer, PaymentVerifySerializer  # Add these
)

# ===========================
#  LOCATION VIEWSETS
# ===========================

class CountryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for countries - read-only for public use"""
    queryset = Country.objects.filter(is_active=True).order_by('sort_order', 'name')
    serializer_class = CountrySerializer
    permission_classes = [AllowAny]
    filterset_class = CountryFilter
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'sort_order']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Cache the queryset for performance
        cache_key = 'countries_active'
        cached_countries = cache.get(cache_key)
        
        if cached_countries is None:
            cached_countries = list(queryset.values())
            cache.set(cache_key, cached_countries, 3600)  # 1 hour
        
        return queryset

    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get popular countries based on product/service listings"""
        popular_countries = Country.objects.filter(
            is_active=True
        ).annotate(
            products_count=Count('products', filter=Q(products__product_status='published')),
            services_count=Count('services', filter=Q(services__service_status='published'))
        ).filter(
            Q(products_count__gt=0) | Q(services_count__gt=0)
        ).order_by('-products_count', '-services_count')[:20]
        
        serializer = self.get_serializer(popular_countries, many=True)
        return Response(serializer.data)


class StateViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for states - read-only for public use"""
    queryset = State.objects.filter(is_active=True).order_by('sort_order', 'name')
    serializer_class = StateSerializer
    permission_classes = [AllowAny]
    filterset_class = StateFilter
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'sort_order']

    def get_queryset(self):
        queryset = super().get_queryset()
        country_id = self.request.query_params.get('country')
        
        if country_id:
            queryset = queryset.filter(country_id=country_id)
        
        return queryset

    @action(detail=False, methods=['get'])
    def by_country(self, request):
        """Get states for a specific country"""
        country_id = request.query_params.get('country_id')
        if not country_id:
            return Response({'error': 'country_id parameter is required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        states = LocationUtils.get_states_by_country(country_id)
        return Response(states)


class CityViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for cities - read-only for public use"""
    queryset = City.objects.filter(is_active=True).order_by('sort_order', 'name')
    serializer_class = CitySerializer
    permission_classes = [AllowAny]
    filterset_class = CityFilter
    search_fields = ['name']
    ordering_fields = ['name', 'sort_order', 'population']

    def get_queryset(self):
        queryset = super().get_queryset()
        state_id = self.request.query_params.get('state')
        country_id = self.request.query_params.get('country')
        
        if state_id:
            queryset = queryset.filter(state_id=state_id)
        elif country_id:
            queryset = queryset.filter(country_id=country_id)
        
        return queryset

    @action(detail=False, methods=['get'])
    def by_state(self, request):
        """Get cities for a specific state"""
        state_id = request.query_params.get('state_id')
        if not state_id:
            return Response({'error': 'state_id parameter is required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        cities = LocationUtils.get_cities_by_state(state_id)
        return Response(cities)

    @action(detail=False, methods=['get'])
    def major_cities(self, request):
        """Get major cities globally or by country"""
        queryset = self.get_queryset().filter(is_major_city=True)
        country_id = request.query_params.get('country')
        
        if country_id:
            queryset = queryset.filter(country_id=country_id)
        
        serializer = self.get_serializer(queryset[:50], many=True)
        return Response(serializer.data)
    


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for categories with optimized counting"""
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CategoryFilter
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'sort_order']

    def get_queryset(self):
        """Optimized queryset to reduce database queries"""
        return Category.objects.filter(is_active=True).select_related(
            'parent'
        ).prefetch_related(
            'subcategories',
            # Prefetch related products and services for efficient counting
            Prefetch(
                'products',
                queryset=Products.objects.filter(product_status='published').only('id', 'category')
            ),
            Prefetch(
                'services', 
                queryset=Services.objects.filter(service_status='published').only('id', 'category')
            )
        ).order_by('sort_order', 'name')

    @action(detail=False, methods=['get'])
    def root_categories(self, request):
        """Get root categories (no parent)"""
        categories = self.get_queryset().filter(parent__isnull=True)
        serializer = self.get_serializer(categories, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def subcategories(self, request, pk=None):
        """Get subcategories for a specific category"""
        category = self.get_object()
        subcategories = category.get_children()
        
        # Apply same optimization to subcategories
        subcategories = subcategories.select_related('parent').prefetch_related(
            'subcategories',
            Prefetch(
                'products',
                queryset=Products.objects.filter(product_status='published').only('id', 'category')
            ),
            Prefetch(
                'services',
                queryset=Services.objects.filter(service_status='published').only('id', 'category')
            )
        )
        
        serializer = self.get_serializer(subcategories, many=True)
        return Response(serializer.data)

# ===========================
#  CORE BUSINESS LOGIC
# ===========================

class StatsAPIView(APIView):
    """Enhanced stats with location-based insights"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        user_products = Products.objects.filter(user=user)
        user_services = Services.objects.filter(user=user)
        
        # Basic stats
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
        
        # Location breakdown
        location_stats = user_products.values(
            'country__name', 'state__name', 'city__name'
        ).annotate(count=Count('id')).order_by('-count')[:10]
        
        stats['top_locations'] = list(location_stats)
        
        # Category breakdown
        category_stats = user_products.values(
            'category__name'
        ).annotate(count=Count('id')).order_by('-count')[:10]
        
        stats['top_categories'] = list(category_stats)
        
        serializer = StatsSerializer(stats)
        return Response(serializer.data)


class HomePageAPIView(APIView):
    """Enhanced home page with proper location filtering"""
    permission_classes = [AllowAny]

    def get(self, request):
        # Get filter parameters
        search_query = request.query_params.get("search", "")
        category_id = request.query_params.get("category")
        country_id = request.query_params.get("country")
        state_id = request.query_params.get("state")
        city_id = request.query_params.get("city")
        min_rating = request.query_params.get("min_rating")
        max_price = request.query_params.get("max_price")

        # Validate location hierarchy
        if city_id and state_id and country_id:
            is_valid, _ = LocationUtils.validate_location_hierarchy(
                country_id, state_id, city_id
            )
            if not is_valid:
                return Response(
                    {'error': 'Invalid location hierarchy'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Base querysets
        products_query = Products.objects.filter(product_status='published')
        services_query = Services.objects.filter(service_status='published')

        # Apply filters
        if search_query:
            products_query = products_query.filter(
                Q(product_name__icontains=search_query) |
                Q(product_description__icontains=search_query) |
                Q(tags__icontains=search_query)
            )
            services_query = services_query.filter(
                Q(service_name__icontains=search_query) |
                Q(service_description__icontains=search_query) |
                Q(tags__icontains=search_query)
            )

        if category_id:
            try:
                category = Category.objects.get(id=category_id, is_active=True)
                # Include subcategories
                all_categories = [category] + category.get_all_subcategories()
                products_query = products_query.filter(category__in=all_categories)
                services_query = services_query.filter(category__in=all_categories)
            except Category.DoesNotExist:
                pass

        # Location filters
        if country_id:
            products_query = products_query.filter(country_id=country_id)
            services_query = services_query.filter(country_id=country_id)
        
        if state_id:
            products_query = products_query.filter(state_id=state_id)
            services_query = services_query.filter(state_id=state_id)
        
        if city_id:
            products_query = products_query.filter(city_id=city_id)
            services_query = services_query.filter(city_id=city_id)

        if max_price:
            try:
                max_price_val = float(max_price)
                products_query = products_query.filter(product_price__lte=max_price_val)
                services_query = services_query.filter(starting_price__lte=max_price_val)
            except ValueError:
                pass

        if min_rating:
            try:
                min_rating_val = float(min_rating)
                products_query = products_query.annotate(
                    avg_rating=Avg("product_ratings__rating")
                ).filter(avg_rating__gte=min_rating_val)
                services_query = services_query.annotate(
                    avg_rating=Avg("service_ratings__rating")
                ).filter(avg_rating__gte=min_rating_val)
            except ValueError:
                pass

        # Log search if there's a query
        if search_query and len(search_query.strip()) > 2:
            SearchHistory.objects.create(
                user=request.user if request.user.is_authenticated else None,
                search_term=search_query.strip(),
                category_id=category_id,
                country_id=country_id,
                state_id=state_id,
                city_id=city_id,
                search_type='both',
                results_count=products_query.count() + services_query.count(),
                ip_address=self.get_client_ip(request)
            )

        # Get results
        promoted_products = products_query.filter(is_promoted=True)[:10]
        promoted_services = services_query.filter(is_promoted=True)[:10]
        products = products_query[:20]
        services = services_query[:20]

        # Filter options for frontend
        filter_options = {
            'countries': LocationUtils.get_countries_json(),
            'categories': list(Category.objects.filter(
                is_active=True, parent__isnull=True
            ).values('id', 'name', 'icon'))
        }

        data = {
            'promoted_products': promoted_products,
            'promoted_services': promoted_services,
            'products': products,
            'services': services,
            'filter_options': filter_options,
            'applied_filters': {
                'search': search_query,
                'category': category_id,
                'country': country_id,
                'state': state_id,
                'city': city_id,
                'min_rating': min_rating,
                'max_price': max_price,
            },
            'total_results': {
                'products': products_query.count(),
                'services': services_query.count()
            }
        }

        serializer = HomePageSerializer(data)
        return Response(serializer.data)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# ===========================
#  PRODUCTS VIEWSET
# ===========================

class ProductsViewSet(viewsets.ModelViewSet):
    """Enhanced Products ViewSet with location system"""
    queryset = Products.objects.select_related(
        'user', 'country', 'state', 'city', 'category'
    ).prefetch_related('product_ratings').order_by('-is_promoted', '-is_featured', '-created_at')
    
    permission_classes = [IsOwnerOrReadOnly]
    filterset_class = ProductsFilter
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['product_name', 'product_description', 'product_brand', 'tags']
    ordering_fields = ['product_price', 'created_at', 'views_count', 'favorites_count']

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
        # Validate location hierarchy before saving
        country_id = serializer.validated_data.get('country').id
        state_id = serializer.validated_data.get('state').id
        city_id = serializer.validated_data.get('city').id
        
        is_valid, _ = LocationUtils.validate_location_hierarchy(
            country_id, state_id, city_id
        )
        
        if not is_valid:
            raise serializers.ValidationError("Invalid location hierarchy")
        
        serializer.save(user=self.request.user, product_status="draft")

    def retrieve(self, request, *args, **kwargs):
        """Override retrieve to increment view count"""
        instance = self.get_object()
        instance.increment_views()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def toggle_favorite(self, request, pk=None):
        """Toggle product favorite status for user"""
        product = self.get_object()
        favorite, created = UserFavorite.objects.get_or_create(
            user=request.user,
            product=product
        )
        
        if not created:
            favorite.delete()
            return Response({'favorited': False})
        
        return Response({'favorited': True})

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def favorites(self, request):
        """Get user's favorite products"""
        favorites = UserFavorite.objects.filter(
            user=request.user, 
            product__isnull=False
        ).select_related('product')
        
        products = [fav.product for fav in favorites]
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def nearby(self, request):
        """Get products near a specific location"""
        city_id = request.query_params.get('city_id')
        if not city_id:
            return Response(
                {'error': 'city_id parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            city = City.objects.get(id=city_id, is_active=True)
            # Get products in same city, then state, then country
            nearby_products = self.get_queryset().filter(
                Q(city=city) |
                Q(state=city.state) |
                Q(country=city.country)
            ).distinct()[:20]
            
            serializer = self.get_serializer(nearby_products, many=True)
            return Response(serializer.data)
            
        except City.DoesNotExist:
            return Response(
                {'error': 'Invalid city_id'}, 
                status=status.HTTP_400_BAD_REQUEST
            )


# ===========================
#  SERVICES VIEWSET
# ===========================

class ServicesViewSet(viewsets.ModelViewSet):
    """Enhanced Services ViewSet with location system"""
    queryset = Services.objects.select_related(
        'user', 'country', 'state', 'city', 'category'
    ).prefetch_related('service_ratings').order_by('-is_promoted', '-is_featured', '-created_at')
    
    permission_classes = [IsOwnerOrReadOnly]
    filterset_class = ServicesFilter
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'service_name', 'service_description', 'provider_name', 
        'provider_expertise', 'tags'
    ]
    ordering_fields = ['starting_price', 'created_at', 'views_count', 'contacts_count']

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
            if self.request.query_params.get('my_services') == 'true':
                if self.request.user.is_authenticated:
                    return queryset.filter(user=self.request.user)
                else:
                    return queryset.none()
            return queryset.filter(service_status='published')
        
        return queryset

    def perform_create(self, serializer):
        # Validate location hierarchy
        country_id = serializer.validated_data.get('country').id
        state_id = serializer.validated_data.get('state').id
        city_id = serializer.validated_data.get('city').id
        
        is_valid, _ = LocationUtils.validate_location_hierarchy(
            country_id, state_id, city_id
        )
        
        if not is_valid:
            raise serializers.ValidationError("Invalid location hierarchy")
        
        serializer.save(user=self.request.user, service_status="draft")

    def retrieve(self, request, *args, **kwargs):
        """Override retrieve to increment view count"""
        instance = self.get_object()
        instance.increment_views()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def contact(self, request, pk=None):
        """Increment contact count when someone contacts service provider"""
        service = self.get_object()
        service.increment_contacts()
        return Response({'detail': 'Contact recorded'})


# ===========================
#  RATING VIEWSETS
# ===========================

class ProductRatingViewSet(viewsets.ModelViewSet):
    serializer_class = ProductRatingSerializer
    permission_classes = [IsOwnerOrReadOnly]
    filterset_class = ProductRatingFilter

    def get_queryset(self):
        return ProductRating.objects.filter(
            product_id=self.kwargs["product_pk"],
            is_active=True
        ).select_related('user').order_by('-created_at')

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
            serializer.save(user=self.request.user, product=product)


class ServiceRatingViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceRatingSerializer
    permission_classes = [IsOwnerOrReadOnly]
    filterset_class = ServiceRatingFilter

    def get_queryset(self):
        return ServiceRating.objects.filter(
            service_id=self.kwargs["service_pk"],
            is_active=True
        ).select_related('user').order_by('-created_at')

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        service = get_object_or_404(Services, pk=self.kwargs["service_pk"])
        
        existing_rating = ServiceRating.objects.filter(
            service=service, 
            user=self.request.user
        ).first()
        
        if existing_rating:
            for attr, value in serializer.validated_data.items():
                setattr(existing_rating, attr, value)
            existing_rating.save()
            return existing_rating
        else:
            serializer.save(user=self.request.user, service=service)


# ===========================
#  UTILITY VIEWS
# ===========================
class LocationCacheAPIView(APIView):
    """Utilize the LocationCache model for better performance"""
    
    def get_cached_location_data(self, cache_key):
        from django.utils import timezone
        
        try:
            cache_entry = LocationCache.objects.get(
                cache_key=cache_key,
                expires_at__gt=timezone.now()
            )
            return cache_entry.cache_data
        except LocationCache.DoesNotExist:
            return None
    
    def set_location_cache(self, cache_key, data, hours=24):
        from django.utils import timezone
        from datetime import timedelta
        
        LocationCache.objects.update_or_create(
            cache_key=cache_key,
            defaults={
                'cache_data': data,
                'expires_at': timezone.now() + timedelta(hours=hours)
            }
        )

class LocationHierarchyAPIView(APIView):
    """Get location hierarchy information"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        city_id = request.query_params.get('city_id')
        state_id = request.query_params.get('state_id')
        country_id = request.query_params.get('country_id')
        
        hierarchy = LocationUtils.get_location_hierarchy(
            city_id=city_id, 
            state_id=state_id, 
            country_id=country_id
        )
        
        if hierarchy:
            return Response(hierarchy)
        else:
            return Response(
                {'error': 'No valid location found'}, 
                status=status.HTTP_404_NOT_FOUND
            )


class SearchAPIView(APIView):
    """Enhanced search with location support"""
    permission_classes = [AllowAny]

    def get(self, request):
        serializer = SearchSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        query = data.get('q', '')
        category = data.get('category', '')
        location = data.get('location', '')
        min_price = data.get('min_price')
        max_price = data.get('max_price')
        min_rating = data.get('min_rating')
        item_type = data.get('item_type', 'all')
        
        results = {}
        
        if item_type in ['all', 'products']:
            products = Products.objects.filter(product_status='published')
            
            if query:
                products = products.filter(
                    Q(product_name__icontains=query) |
                    Q(product_description__icontains=query) |
                    Q(product_brand__icontains=query) |
                    Q(tags__icontains=query)
                )
            
            if category:
                products = products.filter(category__name__icontains=category)
            
            if location:
                products = products.filter(
                    Q(city__name__icontains=location) |
                    Q(state__name__icontains=location) |
                    Q(country__name__icontains=location)
                )
            
            if min_price:
                products = products.filter(product_price__gte=min_price)
                
            if max_price:
                products = products.filter(product_price__lte=max_price)
            
            if min_rating:
                products = products.annotate(
                    avg_rating=Avg('product_ratings__rating')
                ).filter(avg_rating__gte=min_rating)
            
            results['products'] = ProductsSerializer(products[:20], many=True).data
        
        if item_type in ['all', 'services']:
            services = Services.objects.filter(service_status='published')
            
            if query:
                services = services.filter(
                    Q(service_name__icontains=query) |
                    Q(service_description__icontains=query) |
                    Q(provider_name__icontains=query) |
                    Q(provider_expertise__icontains=query) |
                    Q(tags__icontains=query)
                )
            
            if category:
                services = services.filter(category__name__icontains=category)
            
            if location:
                services = services.filter(
                    Q(city__name__icontains=location) |
                    Q(state__name__icontains=location) |
                    Q(country__name__icontains=location)
                )
            
            if min_price:
                services = services.filter(starting_price__gte=min_price)
                
            if max_price:
                services = services.filter(starting_price__lte=max_price)
            
            if min_rating:
                services = services.annotate(
                    avg_rating=Avg('service_ratings__rating')
                ).filter(avg_rating__gte=min_rating)
            
            results['services'] = ServicesSerializer(services[:20], many=True).data
        
        # Log search
        if query and len(query.strip()) > 2:
            SearchHistory.objects.create(
                user=request.user if request.user.is_authenticated else None,
                search_term=query.strip(),
                search_type=item_type,
                results_count=len(results.get('products', [])) + len(results.get('services', [])),
                ip_address=self.get_client_ip(request)
            )
        
        return Response({
            'results': results,
            'query': query,
            'filters_applied': {
                'category': category,
                'location': location,
                'price_range': [min_price, max_price] if min_price or max_price else None,
                'min_rating': min_rating
            }
        })

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# ===========================
#  TRENDING & ANALYTICS VIEWS
# ===========================

class TrendingSearchesAPIView(APIView):
    """Get trending search terms"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        from django.utils import timezone
        from datetime import timedelta
        
        # Get trending searches from last 7 days
        week_ago = timezone.now() - timedelta(days=7)
        
        trending_searches = SearchHistory.objects.filter(
            created_at__gte=week_ago
        ).values('search_term').annotate(
            search_count=Count('id'),
            avg_results=Avg('results_count')
        ).filter(
            search_count__gt=1,
            avg_results__gt=0
        ).order_by('-search_count')[:20]
        
        return Response({
            'trending_searches': list(trending_searches),
            'period': '7 days'
        })


class PopularCategoriesAPIView(APIView):
    """Get popular categories with counts"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        location_filter = {}
        country_id = request.query_params.get('country_id')
        state_id = request.query_params.get('state_id')
        city_id = request.query_params.get('city_id')
        
        if city_id:
            location_filter = {'city_id': city_id}
        elif state_id:
            location_filter = {'state_id': state_id}
        elif country_id:
            location_filter = {'country_id': country_id}
        
        # Get categories with product/service counts
        categories = Category.objects.filter(
            is_active=True,
            parent__isnull=True  # Root categories only
        ).annotate(
            products_count=Count(
                'products',
                filter=Q(products__product_status='published', **{f'products__{k}': v for k, v in location_filter.items()})
            ),
            services_count=Count(
                'services',
                filter=Q(services__service_status='published', **{f'services__{k}': v for k, v in location_filter.items()})
            ),
            total_count=Count('products', filter=Q(products__product_status='published')) + 
                       Count('services', filter=Q(services__service_status='published'))
        ).filter(
            Q(products_count__gt=0) | Q(services_count__gt=0)
        ).order_by('-total_count')[:15]
        
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)


class UserDashboardAPIView(APIView):
    """Enhanced user dashboard with analytics"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        from datetime import timedelta
        from django.utils import timezone
        
        # Get user's listings
        user_products = Products.objects.filter(user=user)
        user_services = Services.objects.filter(user=user)
        
        # Basic counts
        dashboard_data = {
            'products': {
                'total': user_products.count(),
                'published': user_products.filter(product_status='published').count(),
                'draft': user_products.filter(product_status='draft').count(),
                'pending': user_products.filter(product_status='pending').count(),
                'sold': user_products.filter(product_status='sold').count(),
            },
            'services': {
                'total': user_services.count(),
                'published': user_services.filter(service_status='published').count(),
                'draft': user_services.filter(service_status='draft').count(),
                'pending': user_services.filter(service_status='pending').count(),
            }
        }
        
        # Recent activity (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        dashboard_data['recent_activity'] = {
            'products_created': user_products.filter(created_at__gte=thirty_days_ago).count(),
            'services_created': user_services.filter(created_at__gte=thirty_days_ago).count(),
            'total_views': sum([p.views_count for p in user_products]) + sum([s.views_count for s in user_services]),
            'total_contacts': sum([s.contacts_count for s in user_services]),
            'total_favorites': UserFavorite.objects.filter(
                Q(product__user=user) | Q(service__user=user)
            ).count()
        }
        
        # Performance metrics
        dashboard_data['performance'] = {
            'avg_product_rating': user_products.annotate(
                avg_rating=Avg('product_ratings__rating')
            ).aggregate(overall_avg=Avg('avg_rating'))['overall_avg'] or 0,
            'avg_service_rating': user_services.annotate(
                avg_rating=Avg('service_ratings__rating')
            ).aggregate(overall_avg=Avg('avg_rating'))['overall_avg'] or 0,
            'total_reviews': ProductRating.objects.filter(product__user=user).count() + 
                           ServiceRating.objects.filter(service__user=user).count()
        }
        
        # Recent listings
        dashboard_data['recent_products'] = ProductsSerializer(
            user_products.order_by('-created_at')[:5], many=True
        ).data
        dashboard_data['recent_services'] = ServicesSerializer(
            user_services.order_by('-created_at')[:5], many=True
        ).data
        
        # Favorites
        user_favorites = UserFavorite.objects.filter(user=user).select_related(
            'product', 'service'
        ).order_by('-created_at')[:10]
        
        dashboard_data['favorites'] = UserFavoriteSerializer(user_favorites, many=True).data
        
        return Response(dashboard_data)


# ===========================
#  ADMIN & MODERATION VIEWS
# ===========================
# Fix the AdminStatsAPIView
class AdminStatsAPIView(APIView):
    """Admin statistics and insights"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        from datetime import timedelta
        
        User = get_user_model()  # Fix this line
        
        today = timezone.now()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Overall statistics
        stats = {
            'overview': {
                'total_users': User.objects.count(),  # Fixed
                'total_products': Products.objects.count(),
                'total_services': Services.objects.count(),
                'total_countries': Country.objects.filter(is_active=True).count(),
                'total_categories': Category.objects.filter(is_active=True).count(),
            },
            # ... rest of your stats code
        }
        
        return Response(stats)

class ModerationQueueAPIView(APIView):
    """Items pending moderation"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        # Items pending approval
        pending_products = Products.objects.filter(
            product_status='pending'
        ).select_related('user', 'category', 'country', 'state', 'city').order_by('-created_at')
        
        pending_services = Services.objects.filter(
            service_status='pending'
        ).select_related('user', 'category', 'country', 'state', 'city').order_by('-created_at')
        
        return Response({
            'pending_products': ProductsSerializer(pending_products[:20], many=True).data,
            'pending_services': ServicesSerializer(pending_services[:20], many=True).data,
            'counts': {
                'total_pending_products': pending_products.count(),
                'total_pending_services': pending_services.count(),
            }
        })


# ===========================
#  REPORTING & ANALYTICS
# ===========================

class ReportsAPIView(APIView):
    """Generate various reports"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        report_type = request.query_params.get('type', 'overview')
        
        if report_type == 'location_performance':
            return self._location_performance_report(request)
        elif report_type == 'category_analysis':
            return self._category_analysis_report(request)
        elif report_type == 'user_activity':
            return self._user_activity_report(request)
        else:
            return self._overview_report(request)
    
    def _location_performance_report(self, request):
        """Report on location-based performance"""
        location_stats = Country.objects.annotate(
            products_count=Count('products', filter=Q(products__product_status='published')),
            services_count=Count('services', filter=Q(services__service_status='published')),
            avg_product_price=Avg('products__product_price', filter=Q(products__product_status='published')),
            avg_service_price=Avg('services__starting_price', filter=Q(services__service_status='published')),
            total_views=Sum('products__views_count') + Sum('services__views_count')
        ).filter(
            Q(products_count__gt=0) | Q(services_count__gt=0)
        ).order_by('-products_count', '-services_count')
        
        return Response({
            'report_type': 'location_performance',
            'data': [{
                'country': country.name,
                'products_count': country.products_count,
                'services_count': country.services_count,
                'avg_product_price': country.avg_product_price,
                'avg_service_price': country.avg_service_price,
                'total_views': country.total_views or 0
            } for country in location_stats]
        })
    
    def _category_analysis_report(self, request):
        """Report on category performance"""
        category_stats = Category.objects.annotate(
            products_count=Count('products', filter=Q(products__product_status='published')),
            services_count=Count('services', filter=Q(services__service_status='published')),
            avg_product_rating=Avg('products__product_ratings__rating'),
            avg_service_rating=Avg('services__service_ratings__rating'),
            total_searches=Count('searchhistory')
        ).filter(
            Q(products_count__gt=0) | Q(services_count__gt=0)
        ).order_by('-products_count', '-services_count')
        
        return Response({
            'report_type': 'category_analysis',
            'data': [{
                'category': category.name,
                'category_type': category.category_type,
                'products_count': category.products_count,
                'services_count': category.services_count,
                'avg_product_rating': category.avg_product_rating,
                'avg_service_rating': category.avg_service_rating,
                'total_searches': category.total_searches
            } for category in category_stats]
        })
    
    def _user_activity_report(self, request):
        """Report on user activity patterns"""
        from django.contrib.auth import get_user_model
        from datetime import timedelta
        from django.utils import timezone
        
        User = get_user_model()
        month_ago = timezone.now() - timedelta(days=30)
        
        active_users = User.objects.annotate(
            products_count=Count('products'),
            services_count=Count('services'),
            recent_products=Count('products', filter=Q(products__created_at__gte=month_ago)),
            recent_services=Count('services', filter=Q(services__created_at__gte=month_ago)),
            total_ratings_given=Count('productrating') + Count('servicerating')
        ).filter(
            Q(products_count__gt=0) | Q(services_count__gt=0)
        ).order_by('-products_count', '-services_count')[:50]
        
        return Response({
            'report_type': 'user_activity',
            'data': [{
                'user_id': user.id,
                'username': user.username,
                'products_count': user.products_count,
                'services_count': user.services_count,
                'recent_products': user.recent_products,
                'recent_services': user.recent_services,
                'total_ratings_given': user.total_ratings_given,
                'date_joined': user.date_joined
            } for user in active_users]
        })
    
    def _overview_report(self, request):
        """General overview report"""
        from datetime import timedelta
        from django.utils import timezone
        
        today = timezone.now()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        return Response({
            'report_type': 'overview',
            'generated_at': today,
            'summary': {
                'total_listings': Products.objects.count() + Services.objects.count(),
                'active_listings': Products.objects.filter(product_status='published').count() + 
                                 Services.objects.filter(service_status='published').count(),
                'listings_this_week': Products.objects.filter(created_at__gte=week_ago).count() + 
                                    Services.objects.filter(created_at__gte=week_ago).count(),
                'listings_this_month': Products.objects.filter(created_at__gte=month_ago).count() + 
                                     Services.objects.filter(created_at__gte=month_ago).count(),
                'total_views': Products.objects.aggregate(total=Sum('views_count'))['total'] or 0 + 
                             Services.objects.aggregate(total=Sum('views_count'))['total'] or 0,
                'total_ratings': ProductRating.objects.count() + ServiceRating.objects.count(),
                'avg_product_rating': ProductRating.objects.aggregate(avg=Avg('rating'))['avg'] or 0,
                'avg_service_rating': ServiceRating.objects.aggregate(avg=Avg('rating'))['avg'] or 0
            }
        })


# ===========================
#  BULK OPERATIONS
# ===========================

class BulkOperationsAPIView(APIView):
    """Handle bulk operations on listings"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        action = request.data.get('action')
        item_type = request.data.get('item_type')  # 'products' or 'services'
        item_ids = request.data.get('item_ids', [])
        
        if not action or not item_type or not item_ids:
            return Response(
                {'error': 'action, item_type, and item_ids are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if item_type == 'products':
            queryset = Products.objects.filter(id__in=item_ids, user=request.user)
        elif item_type == 'services':
            queryset = Services.objects.filter(id__in=item_ids, user=request.user)
        else:
            return Response({'error': 'Invalid item_type'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not queryset.exists():
            return Response({'error': 'No items found or access denied'}, 
                          status=status.HTTP_404_NOT_FOUND)
        
        # Perform bulk action
        updated_count = 0
        
        if action == 'delete':
            updated_count = queryset.count()
            queryset.delete()
        elif action == 'publish':
            if item_type == 'products':
                updated_count = queryset.update(product_status='published')
            else:
                updated_count = queryset.update(service_status='published')
        elif action == 'draft':
            if item_type == 'products':
                updated_count = queryset.update(product_status='draft')
            else:
                updated_count = queryset.update(service_status='draft')
        elif action == 'feature':
            updated_count = queryset.update(is_featured=True)
        elif action == 'unfeature':
            updated_count = queryset.update(is_featured=False)
        else:
            return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': True,
            'action': action,
            'item_type': item_type,
            'updated_count': updated_count
        })


# ===========================
#  EXPORT FUNCTIONALITY
# ===========================

class ExportDataAPIView(APIView):
    """Export user data"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        export_type = request.query_params.get('type', 'all')
        format_type = request.query_params.get('format', 'json')
        
        user = request.user
        export_data = {}
        
        if export_type in ['all', 'products']:
            products = Products.objects.filter(user=user).values(
                'product_name', 'product_description', 'product_price', 
                'product_condition', 'product_status', 'created_at',
                'category__name', 'country__name', 'state__name', 'city__name'
            )
            export_data['products'] = list(products)
        
        if export_type in ['all', 'services']:
            services = Services.objects.filter(user=user).values(
                'service_name', 'service_description', 'starting_price',
                'service_status', 'provider_name', 'created_at',
                'category__name', 'country__name', 'state__name', 'city__name'
            )
            export_data['services'] = list(services)
        
        if export_type in ['all', 'ratings']:
            product_ratings = ProductRating.objects.filter(user=user).values(
                'product__product_name', 'rating', 'review', 'created_at'
            )
            service_ratings = ServiceRating.objects.filter(user=user).values(
                'service__service_name', 'rating', 'review', 'created_at'
            )
            export_data['ratings'] = {
                'product_ratings': list(product_ratings),
                'service_ratings': list(service_ratings)
            }
        
        export_data['exported_at'] = timezone.now()
        export_data['user'] = user.username
        
        if format_type == 'csv':
            # For CSV export, you'd need to implement CSV conversion
            # This is a simplified JSON response
            response = Response(export_data)
            response['Content-Disposition'] = 'attachment; filename="export.json"'
            return response
        
        return Response(export_data)


# ===========================
#  HEALTH CHECK & STATUS
# ===========================

class HealthCheckAPIView(APIView):
    """API health check endpoint"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        from django.db import connection
        
        try:
            # Test database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            # Basic statistics
            stats = {
                'status': 'healthy',
                'timestamp': timezone.now(),
                'database': 'connected',
                'version': '1.0.0',
                'active_countries': Country.objects.filter(is_active=True).count(),
                'total_listings': Products.objects.count() + Services.objects.count(),
                'published_listings': Products.objects.filter(product_status='published').count() + 
                                    Services.objects.filter(service_status='published').count()
            }
            
            return Response(stats)
            
        except Exception as e:
            return Response({
                'status': 'unhealthy',
                'timestamp': timezone.now(),
                'error': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class APIVersionAPIView(APIView):
    """API version and documentation links"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        return Response({
            'api_version': '1.0.0',
            'django_version': '4.2+',
            'endpoints': {
                'countries': '/api/countries/',
                'states': '/api/states/',
                'cities': '/api/cities/',
                'categories': '/api/categories/',
                'products': '/api/products/',
                'services': '/api/services/',
                'search': '/api/search/',
                'homepage': '/api/homepage/',
                'stats': '/api/stats/',
                'health': '/api/health/'
            },
            'features': [
                'Location hierarchy validation',
                'Advanced search and filtering',
                'Rating and review system',
                'User favorites',
                'Bulk operations',
                'Analytics and reporting',
                'Export functionality',
                'Caching optimization'
            ]
        })

class PaystackInitiatePaymentAPIView(APIView):
    """Initialize Paystack payment for product or service listing"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = PaymentInitiateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        product_id = serializer.validated_data.get('product_id')
        service_id = serializer.validated_data.get('service_id')
        
        base_listing_fee = 1000  # Base fee in Naira
        item_name = ""
        order_id = None
        total_fee = base_listing_fee
        item_type = ""
        
        # Validate that only one ID is provided
        if product_id and service_id:
            return Response(
                {'error': 'Provide either product_id or service_id, not both'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not product_id and not service_id:
            return Response(
                {'error': 'Either product_id or service_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get item details and calculate fees
        if product_id:
            try:
                item = get_object_or_404(Products, id=product_id, user=request.user)
                item_name = f"Product Listing Fee - {item.product_name}"
                order_id = product_id
                item_type = 'product'
                
                # Check if already paid
                if item.is_paid:
                    return Response(
                        {'error': 'This product listing has already been paid for'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Add promotion fee if applicable
                if item.is_promoted:
                    total_fee += float(item.promotion_fee)
                    
            except Products.DoesNotExist:
                return Response(
                    {'error': 'Product not found or you don\'t have permission to pay for it'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        elif service_id:
            try:
                item = get_object_or_404(Services, id=service_id, user=request.user)
                item_name = f"Service Listing Fee - {item.service_name}"
                order_id = service_id
                item_type = 'service'
                
                # Check if already paid
                if item.is_paid:
                    return Response(
                        {'error': 'This service listing has already been paid for'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Add promotion fee if applicable
                if item.is_promoted:
                    total_fee += float(item.promotion_fee)
                    
            except Services.DoesNotExist:
                return Response(
                    {'error': 'Service not found or you don\'t have permission to pay for it'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Prepare Paystack payment data
        email = request.user.email
        
        if not email:
            return Response(
                {'error': 'User email is required for payment'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        headers = {
            'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
            'Content-Type': 'application/json',
        }
        
        # Build callback URL for API
        callback_url = request.build_absolute_uri('/api/payment/paystack/callback/')
        
        paystack_data = {
            'amount': int(total_fee * 100),  # Convert to Kobo
            'email': email,
            'callback_url': callback_url,
            'metadata': {
                'order_id': order_id,
                'item_type': item_type,
                'user_id': request.user.id,
                'item_name': item_name,
                'base_fee': base_listing_fee,
                'total_fee': total_fee,
                'is_promoted': item.is_promoted,
                'promotion_fee': float(item.promotion_fee) if item.is_promoted else 0,
            },
            'channels': ['card', 'bank', 'ussd', 'qr', 'mobile_money', 'bank_transfer'],
        }
        
        try:
            # Make request to Paystack
            response = requests.post(
                settings.PAYSTACK_PAYMENT_URL, 
                json=paystack_data, 
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                paystack_response = response.json()
                
                if paystack_response.get('status'):
                    authorization_url = paystack_response['data']['authorization_url']
                    reference = paystack_response['data']['reference']
                    
                    # Update item status to pending payment
                    if item_type == 'product':
                        item.product_status = 'pending'
                    else:
                        item.service_status = 'pending'
                    item.save()
                    
                    return Response({
                        'success': True,
                        'message': 'Payment initialized successfully',
                        'data': {
                            'authorization_url': authorization_url,
                            'reference': reference,
                            'amount': total_fee,
                            'item_name': item_name,
                            'item_type': item_type,
                            'order_id': order_id,
                            'callback_url': callback_url
                        }
                    })
                else:
                    return Response(
                        {'error': f'Paystack error: {paystack_response.get("message", "Unknown error")}'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                return Response(
                    {'error': 'Payment initialization failed. Please try again.'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except requests.exceptions.RequestException as e:
            return Response(
                {'error': f'Network error: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {'error': f'Payment initialization failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaystackCallbackAPIView(APIView):
    """Handle Paystack payment callback and verify transaction"""
    permission_classes = []  # Allow unauthenticated access for callbacks
    
    def get(self, request):
        reference = request.query_params.get('reference')
        
        if not reference:
            return Response(
                {'error': 'No payment reference provided'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return self._verify_payment(reference)
    
    def post(self, request):
        """Handle webhook callbacks from Paystack"""
        reference = request.data.get('reference')
        
        if not reference:
            return Response(
                {'error': 'No payment reference provided'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return self._verify_payment(reference)
    
    def _verify_payment(self, reference):
        """Verify payment with Paystack and update item status"""
        headers = {
            'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
            'Content-Type': 'application/json',
        }
        
        verify_url = f'https://api.paystack.co/transaction/verify/{reference}'
        
        try:
            response = requests.get(verify_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                paystack_response = response.json()
                
                if paystack_response.get('status'):
                    data = paystack_response.get('data', {})
                    transaction_status = data.get('status')
                    metadata = data.get('metadata', {})
                    
                    order_id = metadata.get('order_id')
                    item_type = metadata.get('item_type')
                    user_id = metadata.get('user_id')
                    amount_paid = data.get('amount', 0) / 100  # Convert from Kobo to Naira
                    
                    if not order_id or not item_type:
                        return Response(
                            {'error': 'Invalid payment metadata'}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    # Verify transaction was successful
                    if transaction_status == 'success':
                        try:
                            # Update item status based on type
                            if item_type == 'product':
                                product = get_object_or_404(Products, id=order_id)
                                
                                # Verify user ownership (security check)
                                if str(product.user.id) != str(user_id):
                                    return Response(
                                        {'error': 'Payment verification failed: User mismatch'}, 
                                        status=status.HTTP_403_FORBIDDEN
                                    )
                                
                                # Update product status
                                product.product_status = 'published'
                                product.is_paid = True
                                product.published_at = timezone.now()
                                product.save()
                                
                                return Response({
                                    'success': True,
                                    'message': 'Product payment successful. Your product is now listed.',
                                    'data': {
                                        'item_type': 'product',
                                        'item_id': order_id,
                                        'item_name': product.product_name,
                                        'amount_paid': amount_paid,
                                        'status': 'published',
                                        'reference': reference,
                                        'published_at': product.published_at
                                    }
                                })
                                
                            elif item_type == 'service':
                                service = get_object_or_404(Services, id=order_id)
                                
                                # Verify user ownership (security check)
                                if str(service.user.id) != str(user_id):
                                    return Response(
                                        {'error': 'Payment verification failed: User mismatch'}, 
                                        status=status.HTTP_403_FORBIDDEN
                                    )
                                
                                # Update service status
                                service.service_status = 'published'
                                service.is_paid = True
                                service.published_at = timezone.now()
                                service.save()
                                
                                return Response({
                                    'success': True,
                                    'message': 'Service payment successful. Your service is now listed.',
                                    'data': {
                                        'item_type': 'service',
                                        'item_id': order_id,
                                        'item_name': service.service_name,
                                        'amount_paid': amount_paid,
                                        'status': 'published',
                                        'reference': reference,
                                        'published_at': service.published_at
                                    }
                                })
                            
                            else:
                                return Response(
                                    {'error': 'Invalid item type in metadata'}, 
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                                
                        except (Products.DoesNotExist, Services.DoesNotExist):
                            return Response(
                                {'error': 'Item not found'}, 
                                status=status.HTTP_404_NOT_FOUND
                            )
                    
                    else:
                        return Response(
                            {'error': f'Payment verification failed. Status: {transaction_status}'}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )
                
                else:
                    return Response(
                        {'error': f'Paystack verification failed: {paystack_response.get("message", "Unknown error")}'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            else:
                return Response(
                    {'error': 'Unable to verify payment at this time'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except requests.exceptions.RequestException as e:
            return Response(
                {'error': f'Network error during verification: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {'error': f'Payment verification failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaymentStatusAPIView(APIView):
    """Check payment status of a product or service"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = PaymentVerifySerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        product_id = serializer.validated_data.get('product_id')
        service_id = serializer.validated_data.get('service_id')
        
        if product_id:
            try:
                item = get_object_or_404(Products, id=product_id, user=request.user)
                return Response({
                    'item_type': 'product',
                    'item_id': product_id,
                    'item_name': item.product_name,
                    'is_paid': item.is_paid,
                    'status': item.product_status,
                    'is_promoted': item.is_promoted,
                    'promotion_fee': float(item.promotion_fee),
                    'published_at': item.published_at,
                    'created_at': item.created_at
                })
            except Products.DoesNotExist:
                return Response(
                    {'error': 'Product not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        elif service_id:
            try:
                item = get_object_or_404(Services, id=service_id, user=request.user)
                return Response({
                    'item_type': 'service',
                    'item_id': service_id,
                    'item_name': item.service_name,
                    'is_paid': item.is_paid,
                    'status': item.service_status,
                    'is_promoted': item.is_promoted,
                    'promotion_fee': float(item.promotion_fee),
                    'published_at': item.published_at,
                    'created_at': item.created_at
                })
            except Services.DoesNotExist:
                return Response(
                    {'error': 'Service not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )


class PaymentHistoryAPIView(APIView):
    """Get user's payment history"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Get paid products
        paid_products = Products.objects.filter(
            user=user, 
            is_paid=True
        ).values(
            'id', 'product_name', 'product_status', 'is_promoted', 
            'promotion_fee', 'published_at', 'created_at'
        ).order_by('-published_at')
        
        # Get paid services
        paid_services = Services.objects.filter(
            user=user, 
            is_paid=True
        ).values(
            'id', 'service_name', 'service_status', 'is_promoted', 
            'promotion_fee', 'published_at', 'created_at'
        ).order_by('-published_at')
        
        # Calculate totals
        base_fee = 1000  # Base listing fee
        
        total_products = paid_products.count()
        total_services = paid_services.count()
        
        total_amount = (total_products + total_services) * base_fee
        
        # Add promotion fees
        for product in paid_products:
            if product['is_promoted']:
                total_amount += float(product['promotion_fee'])
        
        for service in paid_services:
            if service['is_promoted']:
                total_amount += float(service['promotion_fee'])
        
        return Response({
            'summary': {
                'total_payments': total_products + total_services,
                'total_products_paid': total_products,
                'total_services_paid': total_services,
                'total_amount_paid': total_amount,
                'base_listing_fee': base_fee
            },
            'paid_products': list(paid_products),
            'paid_services': list(paid_services)
        })


# ===========================
#  PROMOTIONAL PAYMENT VIEWS
# ===========================

class PromoteItemAPIView(APIView):
    """Promote an existing published item"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        item_type = request.data.get('item_type')  # 'product' or 'service'
        item_id = request.data.get('item_id')
        promotion_duration = request.data.get('promotion_duration', 30)  # days
        
        if not item_type or not item_id:
            return Response(
                {'error': 'item_type and item_id are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate promotion fee based on duration
        daily_promotion_fee = 50  # Naira per day
        total_promotion_fee = daily_promotion_fee * promotion_duration
        
        try:
            if item_type == 'product':
                item = get_object_or_404(Products, id=item_id, user=request.user)
                
                if not item.is_paid or item.product_status != 'published':
                    return Response(
                        {'error': 'Only published and paid products can be promoted'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                if item.is_promoted:
                    return Response(
                        {'error': 'This product is already promoted'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                item_name = f"Promotion Fee - {item.product_name}"
                
            elif item_type == 'service':
                item = get_object_or_404(Services, id=item_id, user=request.user)
                
                if not item.is_paid or item.service_status != 'published':
                    return Response(
                        {'error': 'Only published and paid services can be promoted'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                if item.is_promoted:
                    return Response(
                        {'error': 'This service is already promoted'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                item_name = f"Promotion Fee - {item.service_name}"
            
            else:
                return Response(
                    {'error': 'Invalid item_type. Use "product" or "service"'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Initialize Paystack payment for promotion
            headers = {
                'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
                'Content-Type': 'application/json',
            }
            
            callback_url = request.build_absolute_uri('/api/payment/paystack/promotion-callback/')
            
            paystack_data = {
                'amount': int(total_promotion_fee * 100),  # Convert to Kobo
                'email': request.user.email,
                'callback_url': callback_url,
                'metadata': {
                    'order_id': item_id,
                    'item_type': item_type,
                    'user_id': request.user.id,
                    'payment_type': 'promotion',
                    'item_name': item_name,
                    'promotion_duration': promotion_duration,
                    'promotion_fee': total_promotion_fee,
                },
                'channels': ['card', 'bank', 'ussd', 'qr', 'mobile_money', 'bank_transfer'],
            }
            
            response = requests.post(
                settings.PAYSTACK_PAYMENT_URL, 
                json=paystack_data, 
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                paystack_response = response.json()
                
                if paystack_response.get('status'):
                    return Response({
                        'success': True,
                        'message': 'Promotion payment initialized successfully',
                        'data': {
                            'authorization_url': paystack_response['data']['authorization_url'],
                            'reference': paystack_response['data']['reference'],
                            'amount': total_promotion_fee,
                            'item_name': item_name,
                            'promotion_duration': promotion_duration,
                            'daily_rate': daily_promotion_fee
                        }
                    })
                else:
                    return Response(
                        {'error': f'Paystack error: {paystack_response.get("message", "Unknown error")}'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                return Response(
                    {'error': 'Promotion payment initialization failed'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except (Products.DoesNotExist, Services.DoesNotExist):
            return Response(
                {'error': 'Item not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Promotion initialization failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PromotionCallbackAPIView(APIView):
    """Handle promotion payment callback"""
    permission_classes = []
    
    def get(self, request):
        reference = request.query_params.get('reference')
        if not reference:
            return Response({'error': 'No reference provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Similar verification logic as main callback but for promotions
        # This would activate the promotion after successful payment
        
        return Response({'message': 'Promotion callback received'})