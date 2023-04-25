from django.contrib.auth import get_user_model
from djoser.conf import settings
from djoser.serializers import UserSerializer, UserCreateSerializer
from hashid_field.rest import HashidSerializerCharField


User = get_user_model()


class ChatUserSerializer(UserSerializer):
    """
    chat user serializer with photo field based on djoser user serializer
    """
    id = HashidSerializerCharField(source_field='users.ChatUser.id', read_only=True)

    class Meta(UserSerializer.Meta):
        fields = tuple(User.REQUIRED_FIELDS) + (
            settings.USER_ID_FIELD,
            settings.LOGIN_FIELD,
            'photo'     ### add photo to fields
        )


class ChatUserCreateSerializer(UserCreateSerializer):
    """
    hash id version of djozer UserCreateSerializer serializer
    """
    id = HashidSerializerCharField(source_field='users.ChatUser.id', read_only=True)

    class Meta(UserCreateSerializer.Meta):
        pass