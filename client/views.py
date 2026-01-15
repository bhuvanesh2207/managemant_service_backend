from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from accounts.authentication import JWTAuthenticationFromCookie
from django.shortcuts import get_object_or_404
from .models import Client
from .serializers import ClientSerializer, ClientCreateSerializer
import logging

logger = logging.getLogger(__name__)


# ---------------- ADD CLIENT ----------------
@api_view(["POST"])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def add_client(request):
    serializer = ClientCreateSerializer(data=request.data)

    if serializer.is_valid():
        client = serializer.save()
        return Response(
            {
                "success": True,
                "client_id": client.id,
                "message": "Client created successfully"
            },
            status=status.HTTP_201_CREATED
        )

    return Response(
        {"success": False, "errors": serializer.errors},
        status=status.HTTP_400_BAD_REQUEST
    )


# ---------------- LIST CLIENTS ----------------
@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def list_clients(request):
    clients = Client.objects.all().order_by("-created_at")
    serializer = ClientSerializer(clients, many=True)

    return Response(
        {"success": True, "clients": serializer.data},
        status=status.HTTP_200_OK
    )


# ---------------- GET CLIENT ----------------
@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def get_client(request, client_id):
    client = get_object_or_404(Client, pk=client_id)
    serializer = ClientSerializer(client)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------- UPDATE CLIENT ----------------
@api_view(['PUT', 'PATCH'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def update_client(request, client_id):
    client = get_object_or_404(Client, pk=client_id)

    serializer = ClientSerializer(
        client,
        data=request.data,
        partial=True
    )

    if serializer.is_valid():
        serializer.save()
        return Response(
            {"success": True, "message": "Client updated successfully"},
            status=status.HTTP_200_OK
        )

    return Response(
        {"success": False, "errors": serializer.errors},
        status=status.HTTP_400_BAD_REQUEST
    )


# ---------------- DELETE CLIENT ----------------
@api_view(['DELETE'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def delete_client(request, client_id):
    client = get_object_or_404(Client, pk=client_id)
    client.delete()

    return Response(
        {"success": True, "message": "Client deleted successfully"},
        status=status.HTTP_200_OK
    )


# ---------------- CLIENT NAMES ----------------
@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def get_client_names(request):
    clients = Client.objects.all().order_by("name")
    data = [{"id": c.id, "name": c.name} for c in clients]

    return Response(
        {"success": True, "clients": data},
        status=status.HTTP_200_OK
    )
