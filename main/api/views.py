from rest_framework import viewsets, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.conf import settings
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
    ServiceRatingSerializer
)
from .permissions import IsOwnerOrReadOnly

# ==== CATEGORY ====
class LocationCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LocationCategory.objects.all()
    serializer_class = LocationCategorySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["category", "state", "city"]

# ==== PRODUCTS ====
class ProductsViewSet(viewsets.ModelViewSet):
    queryset = Products.objects.all().order_by("-is_promoted", "-id")
    serializer_class = ProductsSerializer
    permission_classes = [IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        "product_category", "product_country",
        "product_state", "product_city",
        "product_status", "is_promoted"
    ]
    search_fields = ["product_name", "product_description"]
    ordering_fields = ["product_price", "is_promoted", "id"]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, product_status="pending")

# ==== SERVICES ====
class ServicesViewSet(viewsets.ModelViewSet):
    queryset = Services.objects.all().order_by("-is_promoted", "-id")
    serializer_class = ServicesSerializer
    permission_classes = [IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        "service_category", "service_country",
        "service_state", "service_city",
        "service_status", "is_promoted"
    ]
    search_fields = ["service_name", "service_description"]
    ordering_fields = ["is_promoted", "id"]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, service_status="pending")

# ==== PRODUCT RATINGS (nested) ====
class ProductRatingViewSet(viewsets.ModelViewSet):
    serializer_class = ProductRatingSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_queryset(self):
        return ProductRating.objects.filter(product_id=self.kwargs["product_pk"])

    def perform_create(self, serializer):
        product = get_object_or_404(Products, pk=self.kwargs["product_pk"])
        serializer.save(user=self.request.user, product=product)

# ==== SERVICE RATINGS (nested) ====
class ServiceRatingViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceRatingSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_queryset(self):
        return ServiceRating.objects.filter(service_id=self.kwargs["service_pk"])

    def perform_create(self, serializer):
        service = get_object_or_404(Services, pk=self.kwargs["service_pk"])
        serializer.save(user=self.request.user, service=service)

# ==== PAYSTACK INITIATE ====
class InitiatePaymentAPIView(APIView):
    permission_classes = [IsOwnerOrReadOnly]

    def post(self, request):
        itype = request.data.get("item_type")
        iid   = request.data.get("item_id")
        if itype == "product":
            item = get_object_or_404(Products, pk=iid, user=request.user)
        elif itype == "service":
            item = get_object_or_404(Services, pk=iid, user=request.user)
        else:
            return Response({"detail":"Invalid item_type"}, status=status.HTTP_400_BAD_REQUEST)

        amount = 1000
        if getattr(item, "is_promoted", False):
            amount += item.promotion_fee

        payload = {
            "amount":      amount * 100,
            "email":       request.user.email,
            "callback_url": request.build_absolute_uri("/api/main/payments/verify/"),
            "metadata":    {"item_type": itype, "item_id": iid},
        }
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type":  "application/json",
        }
        resp = requests.post(settings.PAYSTACK_PAYMENT_URL, json=payload, headers=headers)
        if resp.status_code != 200:
            return Response(resp.json(), status=status.HTTP_502_BAD_GATEWAY)

        data = resp.json()["data"]
        return Response({
            "authorization_url": data["authorization_url"],
            "reference":        data["reference"],
        })

# ==== PAYSTACK VERIFY ====
class VerifyPaymentAPIView(APIView):
    permission_classes = []

    def get(self, request):
        ref = request.query_params.get("reference")
        if not ref:
            return Response({"detail":"Missing reference"}, status=status.HTTP_400_BAD_REQUEST)

        verify_url = f"https://api.paystack.co/transaction/verify/{ref}"
        headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
        resp = requests.get(verify_url, headers=headers)
        if resp.status_code != 200:
            return Response(resp.json(), status=status.HTTP_502_BAD_GATEWAY)

        data = resp.json()["data"]
        meta = data.get("metadata", {})
        itype, iid = meta.get("item_type"), meta.get("item_id")

        if data.get("status") == "success":
            if itype == "product":
                obj = get_object_or_404(Products, pk=iid)
                obj.product_status = "published"
            else:
                obj = get_object_or_404(Services, pk=iid)
                obj.service_status = "published"
            obj.is_paid = True
            obj.save()
            return Response({"detail":"Payment verified and item published."})

        return Response({"detail":"Payment not successful."}, status=status.HTTP_400_BAD_REQUEST)
