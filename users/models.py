from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractUser
from hashid_field import HashidAutoField
from encrypted_model_fields.fields import EncryptedCharField, EncryptedEmailField
from chat.permissions import permission, no_permission
from .validator import UnicodeUsernameValidator


class ChatUser(AbstractUser):
    """
    model class for users
    """

    username_validator = UnicodeUsernameValidator()

    def __init__(self, *args, **kwargs) -> None:
        self._role = None
        self._action_permission = no_permission()
        super().__init__(*args, **kwargs)

    id = HashidAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')
    photo = models.ImageField(upload_to='user_picture', null=True)
    username = models.CharField(
        _("username"),
        max_length=150,
        unique=True,
        help_text=_(
            "Required. 150 characters or fewer. Letters, digits only."
        ),
        validators=[username_validator],
        error_messages={
            "unique": _("A user with that username already exists."),
        },
    )
    first_name = EncryptedCharField(
        _("first name"), max_length=150, blank=True)
    last_name = EncryptedCharField(_("last name"), max_length=150, blank=True)
    email = EncryptedEmailField(_("email address"), blank=True, unique=True)
    phone = EncryptedCharField(_("phone number"), max_length=13, null=True)

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
        if self.action_permission == no_permission():
            """
            user action_permission property has not been set 
            """
            return False
        if self.action_permission % permission(action) == 0:
            return True
        else:
            return False
    
    class Meta(AbstractUser.Meta):
        swappable = 'AUTH_USER_MODEL'