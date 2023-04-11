from django.db import models
from django.contrib.auth.models import AbstractUser


class ChatUser(AbstractUser):
    """
    model class for users
    """

    def __init__(self, *args, **kwargs) -> None:
        self._role = None
        super().__init__(*args, **kwargs)

    photo = models.ImageField(upload_to='files', null=True)

    @property
    def role(self):
        """
        user role in a chat room
        fill based on query
        """
        return self._role

    @role.setter
    def role(self, role=None):
         self._role = role
    
    class Meta(AbstractUser.Meta):
        swappable = 'AUTH_USER_MODEL'