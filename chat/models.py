import os
import time
from datetime import datetime
from django.db import models
from django.conf import settings
from django.dispatch import receiver
from django.db.models import Count
from django.db.models.signals import post_save
from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django_eventstream import send_event
from core.base_model import BaseModel, BaseModelManager
from chat.validators import file_validator
from chat.utils import VIDEO_FORMAT, IMAGE_FORMATS, capture_video, blur_image


UserModel = get_user_model()


class ChatRoomManager(BaseModelManager):
    """
    custom manager for chat room
    """

    def update(self, **kwargs):
        """
        update only open chat rooms
        save close time
        """
        closed = kwargs.get('closed', False)
        if closed:
            return super().filter(closed=False, closed_at__isnull=True).update(**kwargs, closed_at=datetime.now())
        super().filter(closed=False).update(**kwargs)


class ChatRoom(BaseModel):
    """
    class model for chat room
    """

    CHATROOM_IMPORTANCE = (
        ("LOW", "LOW"),
        ("MEDIUM", "MEDIUM"),
        ("HIGH", "HIGH"),
    )

    CHATROOM_TYPE = (
        ("TICKET", "TICKET"),
        ("GROUPE", "GROUPE"),
        ("PRIVATE", "PRIVATE"),
    )

    name = models.CharField(max_length=20)
    closed = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True)
    importance = models.CharField(
        max_length=10, choices=CHATROOM_IMPORTANCE, default="LOW")
    type = models.CharField(
        max_length=10, choices=CHATROOM_TYPE, default="TICKET")

    objects = ChatRoomManager()

    @property
    def members(self) -> list:
        """
        return list of chat room members
        """
        qs = self.chat_room_member.select_related("profile")
        profiles = [obj.profile for obj in qs]
        return profiles

    @property
    def left_members(self):
        """
        return query set of chat room left members
        """
        return self.chat_room_member.filter(
            chat_room_id=self.id,
            is_deleted=True
        )

    @property
    def number_of_members(self) -> int:
        """
        return number of chat room members
        """
        c = self.chat_room_member.count()
        return c

    def close(self) -> None:
        """
        close chat room
        """
        self.closed = True
        self.closed_at = datetime.now()

    def accepts_new_member(self) -> bool:
        """
        check if chat room accepts new member
        """
        number_of_members = self.number_of_members
        if self.type == "TICKET" and number_of_members != 0:
            return False
        elif self.type == "PRIVATE" and number_of_members > 1:
            return False
        return True

    def has_member(self, profile_id: int or str) -> bool:
        """
        check if a profile is chat room member or not
        """
        if self.chat_room_member.filter(
            chat_room_id=self.id,
            profile_id=profile_id
        ).exists():
            return True
        return False

    def join(self, profile_id: int or str) -> None:
        """
        join profile to chat room
        NOTICE: check chat room accepts new member befor join
        """
        if self.number_of_members == 0:
            is_creator = True
        else:
            is_creator = False
        self.chat_room_member.create(
            chat_room_id=self.id,
            profile_id=profile_id,
            is_creator=is_creator
        )

    def leave(self, profile_id: int or str) -> None:
        """
        leave profile from chat room
        NOTICE: check chat room has this member
        """
        if self.type == "GROUPE":
            self.chat_room_member.filter(
                chat_room_id=self.id,
                profile_id=profile_id
            ).update(is_deleted=True)

    class Meta:
        db_table = 'chat_rooms'


class ChatRoomMember(BaseModel):
    """
    class model for chat room members
    """
    is_creator = models.BooleanField(default=False)
    chat_room = models.ForeignKey(ChatRoom, related_name=_(
        'chat_room_member'), on_delete=models.CASCADE)
    profile = models.ForeignKey(UserModel, related_name=_(
        'profile_member'), on_delete=models.CASCADE)

    class Meta:
        db_table = 'chat_members'
        constraints = [
            models.UniqueConstraint(
                fields=['chat_room', 'profile'], name='unique_profile_room')
        ]


class ChatUpload(BaseModel):
    """
    chat file upload
    """

    FILE_TYPE = (
        ("VOICE", "VOICE"),
        ("FILE", "FILE"),
        ("VIDEO", "VIDEO"),
        ("IMAGE", "IMAGE"),
    )

    file = models.FileField(upload_to=_('chat_files'))
    file_pic = models.FileField(upload_to=_(
        'chat_files'), null=True)
    file_type = models.CharField(
        max_length=10, choices=FILE_TYPE)

    @property
    def size(self) -> int:
        """
        return size of file
        """
        return self.file.size

    @property
    def format(self) -> str:
        """
        return format of file
        """
        _, file_format = os.path.splitext(self.file.path)
        return file_format

    def instance(self):
        """
        return current instance
        """
        return self.__class__.objects.filter(id=self.id)

    def clean(self) -> None:
        """
        validate data
        """
        file_validator(self.file_type, self.format, self.size)
        return super().clean()

    def save(self, *args, **kwargs) -> None:
        if self.instance().exists():
            super().save(*args, **kwargs)
        else:
            self.file.name = str(round(time.time())) + \
                self.file.name.replace(" ", "_")
            if self.file_type in ["IMAGE", "VIDEO"]:
                if self.file.name.endswith(VIDEO_FORMAT+IMAGE_FORMATS):
                    self.file_pic.name = "chat_files/blured_" + \
                        self.file.name.replace(self.format, ".png")
                    super().save(*args, **kwargs)
                    if self.file.name.endswith(VIDEO_FORMAT):
                        """
                        capture a picture from video file
                        """
                        capture_video(self.file.path)
                    elif self.file.name.endswith(IMAGE_FORMATS):
                        """
                        blur picture
                        """
                        blur_image(self.file.path)
            else:
                super().save(*args, **kwargs)

    class Meta:
        db_table = 'chat_uploads'


class MessageManager(BaseModelManager):
    """
    custom manager for message
    """
    limit = settings.MESSAGE_LIMITE

    def seen(self, chat_room_id: int or str, user_id: int or str) -> int:
        """
        seen MESSAGE_LIMITE messages
        """
        updates = self.get_queryset().filter(
            chat_room_id=chat_room_id).exclude(
                user_id=user_id).order_by("-created_at")[:self.limit].update(seen=True)
        if updates:
            send_unread_messages(chat_room_id)

    def update(self, **kwargs) -> int:
        """
        save seen time
        """
        seen = kwargs.get('seen', False)
        if seen:
            return super().filter(seen_at__isnull=True).update(**kwargs, seen_at=datetime.now())
        super().update(**kwargs)


class Message(BaseModel):
    """
    class model for message
    """
    text = models.TextField(null=True)
    seen = models.BooleanField(default=False)
    seen_at = models.DateTimeField(null=True)
    file = models.OneToOneField(ChatUpload, related_name=_(
        'file_message'), on_delete=models.CASCADE, null=True)
    chat_room = models.ForeignKey(ChatRoom, related_name=_(
        'chat_room_message'), on_delete=models.CASCADE)
    sender = models.ForeignKey(UserModel, related_name=_(
        'sender_message'), on_delete=models.CASCADE)
    reply_to = models.ForeignKey('self', related_name=_(
        'reply_to_message'), on_delete=models.SET_NULL, null=True)

    objects = MessageManager()

    def clean(self) -> None:
        """
        prevent no content message
        """
        if self.text == "":
            self.text = None
        if not (self.text and self.file):
            raise ValidationError("Message with no content is not valid.")
        return super().clean()

    class Meta:
        db_table = 'messages'


def unread_messages(user_id):
    """
    return sse message for a user id
    """
    msg = Message.objects.filter(sender_id=user_id)
    last_msg = msg.order_by('chat_room', '-created_at').distinct(
        'chat_room').values('chat_room', 'text', 'file__file_type', 'created_at')
    u_msg = msg.filter(seen=False).exclude(sender=user_id).values(
        'chat_room').annotate(unread_messages=Count('seen'))
    for obj in last_msg:
        obj['unread_messages'] = 0
        obj['file_type'] = obj['file__file_type']
        obj.pop('file__file_type')
        for msg in u_msg:
            if obj['chat_room'] == msg['chat_room']:
                obj['unread_messages'] = msg['unread_messages']
    lst = list(last_msg)
    return lst


def send_unread_messages(chat_room_id):
    """
    send unread message sse to all chat room members
    """
    members = ChatRoom.objects.get(id=chat_room_id).members
    for profile in members:
        if profile:
            send_event('unread_messages_{}'.format(profile.id),
                            'message', unread_messages(profile.id))


@receiver(post_save, sender=Message)
def sse_signal(sender, instance, **kwargs):
    """
    send unread message sse to chat room members on new message 
    """
    members = instance.chat_room.members
    for profile in members:
        if profile:
            send_event('unread_messages_{}'.format(profile.id),
                            'message', unread_messages(profile.id))


class PredefindMessage(BaseModel):
    """
    class model for predefind message
    """
    text = models.TextField(null=True)
    file = models.OneToOneField(
        ChatUpload, related_name=_('file_predefinedmessage'), on_delete=models.CASCADE, null=True)

    def clean(self) -> None:
        """
        prevent no content message
        """
        if self.text == "":
            self.text = None
        if self.text is None and self.file is None:
            raise ValidationError("Message with no content is not valid.")
        return super().clean()

    class Meta:
        db_table = 'predefind_messages'


class Report(BaseModel):
    """
    class model for report message
    """
    message = models.ForeignKey(
        PredefindMessage, related_name=_('predefinedmessage_report'), on_delete=models.CASCADE)
    reporter = models.ForeignKey(UserModel, related_name=_(
        'reporter_report'), on_delete=models.CASCADE)
    reportee = models.ForeignKey(UserModel, related_name=_(
        'reportee_report'), on_delete=models.CASCADE)

    class Meta:
        db_table = 'reports'
