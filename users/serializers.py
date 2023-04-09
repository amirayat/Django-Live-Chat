from rest_framework import serializers
from django.contrib.auth import get_user_model
from djoser.conf import settings
from djoser.serializers import UserSerializer


User = get_user_model()


class ChatUserSerializer(UserSerializer):
    """
    chat user serializer with photo field based on djoser user serializer
    """
    class Meta(UserSerializer.Meta):
        fields = tuple(User.REQUIRED_FIELDS) + (
            settings.USER_ID_FIELD,
            settings.LOGIN_FIELD,
            'photo'     ### add photo to fields
        )


class MemberSerializer(serializers.ModelSerializer):
    """
    serializer to show chat room members
    """
    class Meta:
        model = User
        fields = ("id","username", "photo")
        read_only_fields = ("id","username", "photo")