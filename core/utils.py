from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.serializers import TokenVerifySerializer
from rest_framework_simplejwt.tokens import AccessToken
from channels.db import database_sync_to_async
from core.base_model import BaseModel


UserModel = get_user_model()


@database_sync_to_async
def get_user_async(token_key):
    try:
        serializer = TokenVerifySerializer(data=token_key)
        if serializer.is_valid():
            access_token = AccessToken(token_key)
            user = UserModel.objects.get(id=access_token['user_id'])
            return user
        else:
            return AnonymousUser()
    except Token.DoesNotExist:
        return AnonymousUser()


def get_user_sync(token_key):
    try:
        serializer = TokenVerifySerializer(data=token_key)
        if serializer.is_valid():
            access_token = AccessToken(token_key)
            user = UserModel.objects.get(id=access_token['user_id'])
            return user
        else:
            return AnonymousUser()
    except Token.DoesNotExist:
        return AnonymousUser()


def fields(model: BaseModel) -> list:
    """
    return desire fields
    """
    fields = [field.name for field in model._meta.fields if field.name not in {
        'updated_at', 'created_at', 'is_deleted'}]
    fields.extend(['id'])
    return fields
