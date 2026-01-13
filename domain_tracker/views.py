from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from .models import Domain, DomainHistory
from .serializers import (
    DomainSerializer,
    DomainCreateSerializer,
    DomainUpdateSerializer,
    DomainHistorySerializer
)
import logging

logger = logging.getLogger(__name__)

# ---------------- CREATE DOMAIN ----------------
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def add_domain(request):
    serializer = DomainCreateSerializer(data=request.data)
    if serializer.is_valid():
        domain = serializer.save()
        logger.info(f"Domain created: {domain.domain_name} by {request.user}")
        return Response(
            {"success": True, "domain_id": domain.id},
            status=status.HTTP_201_CREATED
        )
    return Response(
        {"success": False, "errors": serializer.errors},
        status=status.HTTP_400_BAD_REQUEST
    )


# ---------------- LIST DOMAINS ----------------
@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def list_domains(request):
    domains = Domain.objects.all().order_by('-id')
    serializer = DomainSerializer(domains, many=True)
    return Response(
        {"success": True, "domains": serializer.data},
        status=status.HTTP_200_OK
    )


# ---------------- GET DOMAIN ----------------
@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_domain(request, domain_id):
    domain = get_object_or_404(Domain, pk=domain_id)
    serializer = DomainSerializer(domain)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------- UPDATE DOMAIN ----------------
@api_view(['PATCH'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def update_domain(request, domain_id):
    domain = get_object_or_404(Domain, pk=domain_id)

    serializer = DomainUpdateSerializer(
        domain,
        data=request.data,
        partial=True
    )

    if serializer.is_valid():
        changes_message = serializer.validated_data.pop("changes_message", "")
        serializer.save()

        DomainHistory.objects.create(
            domain=domain,
            changes=changes_message,
            updated_by=request.user
        )

        logger.info(f"Domain updated: {domain.domain_name} by {request.user}")
        return Response(
            {"success": True, "message": "Domain updated and history recorded"},
            status=status.HTTP_200_OK
        )

    return Response(
        {"success": False, "errors": serializer.errors},
        status=status.HTTP_400_BAD_REQUEST
    )


# ---------------- DELETE DOMAIN ----------------
@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def delete_domain(request, domain_id):
    domain = get_object_or_404(Domain, pk=domain_id)
    domain.delete()

    logger.info(f"Domain deleted: {domain.domain_name} by {request.user}")
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------- DOMAIN HISTORY ----------------
@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_domain_history(request, domain_id=None):
    qs = DomainHistory.objects.all()
    if domain_id:
        qs = qs.filter(domain_id=domain_id)

    serializer = DomainHistorySerializer(
        qs.order_by("-updated_at"),
        many=True
    )

    return Response(
        {"success": True, "history": serializer.data},
        status=status.HTTP_200_OK
    )
