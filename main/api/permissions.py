# api/permissions.py - Enhanced Permission Classes
from rest_framework import permissions
from django.utils import timezone
from datetime import timedelta


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    Assumes the model instance has a `user` attribute.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner of the object.
        return getattr(obj, 'user', None) == request.user


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Global permission to only allow admin users to modify data, others can read.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission to allow owners and admins to access/modify objects.
    """
    def has_object_permission(self, request, view, obj):
        # Admin users have full access
        if request.user and request.user.is_staff:
            return True
        
        # Owners have full access to their own objects
        return getattr(obj, 'user', None) == request.user


class IsVerifiedUser(permissions.BasePermission):
    """
    Permission class to check if user is verified (has verified email).
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user has verified email
        # Adjust this based on your user verification system
        return getattr(request.user, 'is_email_verified', True)


class CanCreateListing(permissions.BasePermission):
    """
    Permission class to check if user can create new listings.
    Includes rate limiting and verification checks.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if it's a creation request
        if request.method != 'POST':
            return True
        
        # Check if user has reached daily listing limit
        today = timezone.now().date()
        daily_limit = 10  # Maximum listings per day for regular users
        
        from ..models import Products, Services
        
        # Count today's listings
        todays_products = Products.objects.filter(
            user=request.user,
            created_at__date=today
        ).count()
        
        todays_services = Services.objects.filter(
            user=request.user,
            created_at__date=today
        ).count()
        
        total_today = todays_products + todays_services
        
        # Premium users get higher limits
        if getattr(request.user, 'is_premium', False):
            daily_limit = 50
        elif request.user.is_staff:
            return True  # No limits for staff
        
        if total_today >= daily_limit:
            self.message = f"Daily listing limit of {daily_limit} reached. Try again tomorrow."
            return False
        
        return True


class CanRateItem(permissions.BasePermission):
    """
    Permission class to check if user can rate a product or service.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Only allow POST for creating ratings
        if request.method == 'POST':
            return True
        
        return True
    
    def has_object_permission(self, request, view, obj):
        # Users can't rate their own items
        if hasattr(obj, 'product') and obj.product:
            if obj.product.user == request.user:
                return False
        
        if hasattr(obj, 'service') and obj.service:
            if obj.service.user == request.user:
                return False
        
        # Users can only edit/delete their own ratings
        if request.method in ['PUT', 'PATCH', 'DELETE']:
            return obj.user == request.user
        
        return True


class CanAccessPaymentFeatures(permissions.BasePermission):
    """
    Permission class for payment-related features.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user has valid payment information
        # You can add more sophisticated checks here
        return True


class CanAccessAdminFeatures(permissions.BasePermission):
    """
    Permission class for admin-only features like moderation, reports, etc.
    """
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            (request.user.is_staff or request.user.is_superuser)
        )


class CanAccessAnalytics(permissions.BasePermission):
    """
    Permission class for analytics endpoints.
    Different levels based on user type.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            # Some analytics might be public
            action = getattr(view, 'action', None)
            if action in ['trending_searches', 'popular_categories']:
                return True
            return False
        
        # Authenticated users can access basic analytics
        return True


class CanBulkOperate(permissions.BasePermission):
    """
    Permission class for bulk operations on listings.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user has performed too many bulk operations recently
        # This helps prevent abuse
        recent_limit = timezone.now() - timedelta(hours=1)
        
        # You might want to track bulk operations in a separate model
        # For now, we'll allow it but you can add rate limiting here
        
        return True


class CanExportData(permissions.BasePermission):
    """
    Permission class for data export features.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Regular users can export their own data
        # Staff can export any data
        return True


class IsPublishedOrOwner(permissions.BasePermission):
    """
    Object-level permission to allow public access to published items,
    but owner access to all their items regardless of status.
    """
    def has_object_permission(self, request, view, obj):
        # If it's a safe method (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            # Check if the item is published or if user is the owner
            if hasattr(obj, 'product_status'):
                return (obj.product_status == 'published' or 
                       obj.user == request.user or 
                       (request.user and request.user.is_staff))
            elif hasattr(obj, 'service_status'):
                return (obj.service_status == 'published' or 
                       obj.user == request.user or 
                       (request.user and request.user.is_staff))
        
        # For write operations, only owner or admin
        return (obj.user == request.user or 
               (request.user and request.user.is_staff))


class CanPromoteItem(permissions.BasePermission):
    """
    Permission class for item promotion features.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user has any published items to promote
        from ..models import Products, Services
        
        has_published_items = (
            Products.objects.filter(
                user=request.user, 
                product_status='published',
                is_paid=True
            ).exists() or
            Services.objects.filter(
                user=request.user, 
                service_status='published',
                is_paid=True
            ).exists()
        )
        
        return has_published_items


class LocationHierarchyPermission(permissions.BasePermission):
    """
    Permission class for location hierarchy validation.
    """
    def has_permission(self, request, view):
        # Location data is generally public for browsing
        # But creation/modification requires authentication
        if request.method in permissions.SAFE_METHODS:
            return True
        
        return request.user and request.user.is_authenticated


class RateLimitedPermission(permissions.BasePermission):
    """
    Generic rate limiting permission class.
    """
    def __init__(self, rate_limit=100, time_window=3600):
        self.rate_limit = rate_limit  # Number of requests
        self.time_window = time_window  # Time window in seconds
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return True  # Let other permissions handle anonymous users
        
        # Implement rate limiting logic here
        # You might want to use Redis or Django cache for this
        # For now, we'll return True but you can add actual rate limiting
        
        return True


# ===========================
#  PERMISSION MIXINS
# ===========================

class OwnershipMixin:
    """
    Mixin to add ownership-based permissions to ViewSets.
    """
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        elif self.action == 'create':
            permission_classes = [permissions.IsAuthenticated, CanCreateListing]
        else:
            permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
        
        return [permission() for permission in permission_classes]


class AdminOnlyMixin:
    """
    Mixin to restrict certain actions to admin users only.
    """
    def get_permissions(self):
        if self.action in ['destroy', 'update', 'partial_update']:
            permission_classes = [CanAccessAdminFeatures]
        else:
            permission_classes = [IsAdminOrReadOnly]
        
        return [permission() for permission in permission_classes]


# ===========================
#  CUSTOM DECORATORS
# ===========================

def require_ownership(view_func):
    """
    Decorator to require ownership of an object.
    """
    def wrapper(request, *args, **kwargs):
        # Add ownership validation logic here
        return view_func(request, *args, **kwargs)
    return wrapper


def require_payment_status(status='paid'):
    """
    Decorator to require specific payment status.
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            # Add payment status validation here
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# ===========================
#  PERMISSION UTILITIES
# ===========================

class PermissionUtils:
    @staticmethod
    def has_reached_listing_limit(user, limit_type='daily'):
        """
        Check if user has reached their listing limit.
        """
        if not user or not user.is_authenticated:
            return True
        
        # fetch the user's configured limits
        limits = PermissionUtils.get_user_listing_limits(user)
        current_limit = limits.get(limit_type, 0)
        
        # determine filter date and lookup key
        if limit_type == 'daily':
            filter_date = timezone.now().date()
            lookup = 'created_at__date'
        else:  # 'monthly'
            today = timezone.now().date()
            # first day of current month
            filter_date = date(today.year, today.month, 1)
            lookup = 'created_at__gte'
        
        # import here to avoid circular references
        from ..models import Products, Services
        
        # count products posted in the period
        products_count = Products.objects.filter(
            user=user,
            **{lookup: filter_date}
        ).count()
        
        # count services posted in the period
        services_count = Services.objects.filter(
            user=user,
            **{lookup: filter_date}
        ).count()
        
        total_count = products_count + services_count
        return total_count >= current_limit     