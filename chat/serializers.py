from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError
from rest_framework.serializers import ModelSerializer, CharField, Serializer, PrimaryKeyRelatedField, ChoiceField, DictField, ListField
from djoser.serializers import UserSerializer
from profanity_filter import ProfanityFilter
from chat.models import ChatUpload, Message, PredefindMessage
from core.utils import fields


UserModel = get_user_model()


class MessageContentSerializer(Serializer):
    """
    serializer for message content
    """
    MESSAGE_CHOICES = (
        ("user_typing", "user_typing"),
        ("user_online", "user_online"),
        ("user_notice", "user_notice"),
        ("chat_message", "chat_message"),
    )
    type = ChoiceField(choices=MESSAGE_CHOICES)
    detail = ListField(child=DictField(), required=False)
    text = CharField(max_length=1000, allow_null=True,
                     allow_blank=False, required=False)
    file = PrimaryKeyRelatedField(
        source='ChatUpload', allow_null=True, required=False, queryset=ChatUpload.objects.all())
    reply_to = PrimaryKeyRelatedField(
        source='Message', allow_null=True, required=False, queryset=Message.objects.all())
    
    def validate(self, attrs):
        pf = ProfanityFilter()
        if attrs["type"] == "chat_message" and attrs.get("text", None) is None and attrs.get("file", None) is None:
            raise ValidationError(
                detail="Message with no content is not valid.", code="user_notice")
        elif attrs["type"] in ["user_typing", "user_online", "user_notice"] and attrs.get("detail", None) is None:
            raise ValidationError(
                detail="Message with no content is not valid.", code="user_notice")
        if attrs.get("text", None) and pf.is_clean(attrs["text"]):
            raise ValidationError(
                detail="Message contain swear word.", code="user_notice")
        return super().validate(attrs)


class UploadSerializer(ModelSerializer):
    """
    serializer class to upload
    """
    class Meta:
        model = ChatUpload
        fields = fields(model)+['size']
        read_only_fields = ("id",)


class MessageSerializer(ModelSerializer):
    """
    serializer class for messages
    """
    sender = UserSerializer(read_only=True)
    file = UploadSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Message
        fields = fields(model)+['created_at']
        read_only_fields = ("id",)


class PredefindMessageSerializer(ModelSerializer):
    """
    serializer class for predefind messages
    """

    class Meta:
        model = PredefindMessage
        fields = fields(model)
        read_only_fields = ("id",)
