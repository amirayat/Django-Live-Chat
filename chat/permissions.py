from rest_framework.permissions import IsAdminUser as IsStaff
from rest_framework.permissions import IsAuthenticated, BasePermission, SAFE_METHODS
from chat.models import *


class IsCreator(IsAuthenticated):
    """
    permission for chat room creator
    """

    def has_object_permission(self, request, view, obj):
        """
        allow only chat room creator
        """
        if obj.creator == request.user:
            return True


class IsAdmin(IsAuthenticated):
    """
    permission for chat room admin
    """

    def has_object_permission(self, request, view, obj):
        """
        allow only chat room creator
        """
        if view.action in ["retrieve", "list", "update", "partial_update"] and \
            request.user in obj.admins:
            return True


class IsMember(IsAuthenticated):
    """
    permission for chat room member
    """

    def has_object_permission(self, request, view, obj):
        """
        allow only chat room member
        """
        if request.method in SAFE_METHODS and obj.has_member(request.user):
            return True


class IsMemberOrCreator(IsAuthenticated):
    """
    permission for chat room member or creator
    """

    def has_object_permission(self, request, view, obj):
        return (IsCreator.has_object_permission(self, request, view, obj) or
                IsMember.has_object_permission(self, request, view, obj))


class IsMemberAndStaff(IsStaff):
    """
    permission for chat room member and staff
    """

    def has_object_permission(self, request, view, obj):
        if obj.has_member(request.user):
            return True