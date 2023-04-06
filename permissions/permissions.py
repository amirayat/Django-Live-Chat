from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.permissions import BasePermission, SAFE_METHODS
from django_eventstream.channelmanager import DefaultChannelManager
from core.utils import get_user_sync
from chat.models import *


class MyChannelManager(DefaultChannelManager):
    """
    sse auth
    """
    global token
    token = None

    def get_channels_for_request(self, request, view_kwargs):
        global token
        token = request.GET.get("token", None)
        return super().get_channels_for_request(request, view_kwargs)

    def can_read_channel(self, user, channel):
        user = get_user_sync(token)
        rcv_user_id = int(channel.split("_")[-1])
        if user and user.id == rcv_user_id:
            return True
        return False


class IsSuperUser(IsAdminUser):
    """
    superuser permission
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)


class IsAuthenticatedSafe(IsAuthenticated):
    """
    permission to authenticated users for safe methodes
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)


class IsSuperUserOrAuthenticatedSafe(BasePermission):
    """
    ticket owner or admin permission
    """

    def has_permission(self, request, view):
        return (IsSuperUser.has_permission(self, request, view) or
                IsAuthenticatedSafe.has_permission(self, request, view))


class AccountPermission(BasePermission):
    """
    permission for accounts based on request method
    """

    def has_permission(self, request, view):
        if view.action == "create":
            return False
        elif view.action == "list":
            if request.user.is_staff:
                return super().has_permission(request, view)
        elif view.action == "destroy":
            if request.user.is_superuser:
                return super().has_permission(request, view)
        elif view.action in ("retrieve", "update", "partial_update"):
            return True

    def has_object_permission(self, request, view, obj):
        if view.action in ("retrieve", "update", "partial_update"):
            if request.user.is_staff:
                return super().has_object_permission(request, view, obj)
            elif obj.id == request.user.id:
                return super().has_object_permission(request, view, obj)


class IsAdminUserOrReadOnly(IsAdminUser):
    """
    permission for staff to do all or read only for any body 
    """

    def has_permission(self, request, view):
        is_admin = super(
            IsAdminUserOrReadOnly,
            self).has_permission(request, view)
        return request.method in SAFE_METHODS or is_admin


class IsAdminUserOrSupplier(IsAdminUser):
    """
    permission for staff and supplier to do all 
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        elif request.user.is_staff:
            return True
        elif request.user.is_supplier and obj.supplier_id == request.user.id:
            return True


class IsAdminUserOrOrderOwner(IsAdminUserOrReadOnly):
    """
    permission for staff to do all or read only for order customer and order supplier
    """

    def has_permission(self, request, view):
        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return super().has_object_permission(request, view, obj)
        elif request.method in SAFE_METHODS or request.user.id in {obj.supplier_id, obj.customer_id}:
            return True
