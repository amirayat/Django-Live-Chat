from django.db import models
from django.contrib.auth.models import AbstractUser


class ChatUser(AbstractUser):
    """
    model class for users
    """
    photo = models.ImageField(upload_to='files', null=True)
    
    class Meta(AbstractUser.Meta):
        swappable = 'AUTH_USER_MODEL'