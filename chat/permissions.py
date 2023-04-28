from rest_framework.permissions import IsAuthenticated


permission_coefficients = {
    "remove_member": 31,
    "update_group": 29,
    "close_group": 23,
    "lock_group": 19,
    "add_member": 17,   # minimum admin permision coef should be greater than join_group*send_message
    "join_group": 5,
    "send_message": 3,
}


def no_permission():
    """
    return a different prime number from permission coefficient numbers
    must be lower than minimum permision coef
    """
    return 2


def permission(*args):
    """
    to multiply coefficients of all given permissions and get final
    """
    result = 1
    for _permission, _coefficient in permission_coefficients.items():
        if _permission in args:
            result *= _coefficient
    if result == 1:
        return no_permission()
    return result


def member_permissions():
    return permission_coefficients['send_message']*permission_coefficients['join_group']


def admin_permissions():
    return member_permissions()*permission_coefficients['add_member']


def creator_permissions():
    result = 1
    for _coefficient in permission_coefficients.values():
        result *= _coefficient
    return result


class IsCreator(IsAuthenticated):
    """
    permission for chat room creator
    """

    def has_object_permission(self, request, view, obj):
        if obj.creator == request.user:
            return True


class IsAdmin(IsAuthenticated):
    """
    permission for chat room admin
    """

    def has_object_permission(self, request, view, obj):
        if obj.has_admin(request.user):
            return True


class IsAdmin_CanUpdate(IsAuthenticated):
    """
    admin with update permission
    """

    def has_object_permission(self, request, view, obj):
        if obj.has_admin(request.user) and request.user in obj.admins_can_update:
            return True


class IsAdmin_CanClose(IsAuthenticated):
    """
    admin with close permission
    """

    def has_object_permission(self, request, view, obj):
        if obj.has_admin(request.user) and request.user in obj.admins_can_close:
            return True


class IsAdmin_CanLock(IsAuthenticated):
    """
    admin with lock permission
    """

    def has_object_permission(self, request, view, obj):
        if obj.has_admin(request.user) and request.user in obj.admins_can_lock:
            return True


class IsAdmin_CanAdd(IsAuthenticated):
    """
    admin with add member permission
    """

    def has_object_permission(self, request, view, obj):
        if obj.has_admin(request.user) and request.user in obj.admins_can_add:
            return True


class IsAdmin_CanRemove(IsAuthenticated):
    """
    admin with remove member permission
    """

    def has_object_permission(self, request, view, obj):
        if obj.has_admin(request.user) and request.user in obj.admins_can_remove:
            return True


class IsMember(IsAuthenticated):
    """
    permission for chat room not staff member
    """

    def has_object_permission(self, request, view, obj):
        """
        allow only chat room member
        """
        if obj.has_member(request.user):
            return True


class IsMemberNotStaff(IsMember):
    """
    permission for chat room not staff member
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and not request.user.is_staff)


class IsAuthenticatedNotStaff(IsAuthenticated):
    """
    permission for chat room not staff authenticated user
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and not request.user.is_staff)


class IsMessageSender(IsAuthenticated):
    """
    permission for message sender
    """

    def has_object_permission(self, request, view, obj):
        if request.user == obj.sender.user:
            return True