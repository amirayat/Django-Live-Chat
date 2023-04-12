from rest_framework.permissions import IsAuthenticated, SAFE_METHODS


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
        if request.method != 'DELETE' and request.user in obj.admins:
            return True


class IsMember(IsAuthenticated):
    """
    permission for chat room not staff member
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and not request.user.is_staff)

    def has_object_permission(self, request, view, obj):
        """
        allow only chat room member
        """
        if request.method in SAFE_METHODS and obj.has_member(request.user):
            return True


class IsStaffMember(IsAuthenticated):
    """
    permission for chat room staff member
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)

    def has_object_permission(self, request, view, obj):
        """
        allow only chat room member
        """
        if request.method in SAFE_METHODS and obj.has_member(request.user):
            return True


class IsMemberWithAction(IsAuthenticated):
    """
    permission for chat room not staff member with PUT, PATCH actions
    exp: actions are needed to leave group
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and not request.user.is_staff)

    def has_object_permission(self, request, view, obj):
        """
        allow only chat room member
        """
        if request.method in ('GET', 'HEAD', 'OPTIONS', 'PUT', 'PATCH') and obj.has_member(request.user):
            return True


class IsStaffMemberWithAction(IsAuthenticated):
    """
    permission for chat room staff member with PUT, PATCH actions
    exp: actions are needed to assign staff to ticket
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)

    def has_object_permission(self, request, view, obj):
        """
        allow only chat room member
        """
        if request.method in ('GET', 'HEAD', 'OPTIONS', 'PUT', 'PATCH') and obj.has_member(request.user):
            return True


class IsAuthenticatedNotStaff(IsAuthenticated):
    """
    permission for chat room not staff authenticated user
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and not request.user.is_staff)
