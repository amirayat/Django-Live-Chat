from django.db import models
from django.contrib.auth.models import AbstractUser
from chat.permissions import permission, no_permission


class ChatUser(AbstractUser):
    """
    model class for users
    """

    def __init__(self, *args, **kwargs) -> None:
        self._role = None
        self._action_permission = no_permission()
        super().__init__(*args, **kwargs)

    photo = models.ImageField(upload_to='user_picture', null=True)

    @property
    def role(self):
        """
        user role in a chat room
        """
        return self._role

    @role.setter
    def role(self, role=None):
         self._role = role

    @property
    def action_permission(self):
        """
        user action_permission in a chat room
        """
        return self._action_permission

    @action_permission.setter
    def action_permission(self, action_permission=None):
         self._action_permission = action_permission

    def has_action_permission(self, action: str) -> bool:
        if self.action_permission == permission(action) == no_permission():
            """
            case of:
                user action_permission property has not been set 
                and
                given action is not defined
            """
            return False
        return True if self.action_permission % permission(action) == 0 else False
    
    class Meta(AbstractUser.Meta):
        swappable = 'AUTH_USER_MODEL'