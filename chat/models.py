import time
import random
from typing import TypeVar
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.functional import cached_property
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.db.models import QuerySet, Subquery, Count, Q, F
from django.utils.translation import gettext as _
from django.contrib.auth import get_user_model
from django_eventstream import send_event
from hashid_field import HashidAutoField
from core.base_model import RootModel, RootModelManager
from .permissions import (permission,
                              creator_permissions,
                              admin_permissions,
                              member_permissions,
                              no_permission)
from .utils import IMAGE_FORMATS, VIDEO_FORMATS, AUDIO_FORMATS


UserModel = get_user_model()


ChatRoomObject = TypeVar("ChatRoomObject", bound=models.Model)
ChatMemberObject = TypeVar("ChatMemberObject", bound=models.Model)


class ChatRoomManager(RootModelManager):
    """
    custom manager for chat room
    """

    def top_public_groups(self):
        """
        return top public groups
        """
        return super().get_queryset().filter(type='PUBLIC_GROUPE')\
            .annotate(c=Count('chat_member')).order_by('-c')

    def update(self, **kwargs):
        """
        update only open chat rooms
        record close time
        """
        if kwargs.get('closed', None):
            return super().update(**kwargs, closed_at=timezone.now())
        return super().update(**kwargs)

    def create(self, creator: UserModel, **kwargs):

        _name = kwargs.get('name', str())
        _priority = kwargs.get('priority', 'LOW')
        _type = kwargs.get('type', 'USER_TICKET')
        _contact = kwargs.get('contact', creator)
        _members = kwargs.get('members', list())

        if _type == 'USER_TICKET':
            return self.create_ticket(name=_name, priority=_priority, creator=creator)

        elif _type == 'PRIVATE_CHAT':
            return self.create_private_chat(creator=creator, contact=_contact)

        elif _type == 'PUBLIC_GROUPE':
            return self.create_group(name=_name, creator=creator, members=_members, type=_type)

        elif _type == 'PRIVATE_GROUPE':
            return self.create_group(name=_name, creator=creator, members=_members, type=_type)

    def create_private_chat(self, creator: UserModel, contact: UserModel) -> ChatRoomObject:
        """
        create private chat for two users
        creator: request.user
        contact: another user 
        """
        _name = str(creator.id)+'.'+creator.username+'_' + \
            str(contact.id)+'.'+contact.username
        private_chat, is_create = ChatRoom.objects.get_or_create(
            name=_name,
            type="PRIVATE_CHAT"
        )
        if is_create:
            ChatMember.objects.bulk_create([
                ChatMember(is_creator=True, chat_room=private_chat,
                           user=creator),
                ChatMember(is_creator=False, chat_room=private_chat,
                           user=contact),
            ])
        return private_chat

    def create_ticket(self, name: str, priority: str, creator: UserModel) -> ChatRoomObject:
        """
        create ticket for request user
        creator: request.user
        """
        ticket = super().create(name=name, priority=priority, type="USER_TICKET")
        # find staff with less open ticket to assing to the current ticket
        staff = UserModel.objects.filter(~Q(id=creator.id) & Q(is_staff=True))\
            .annotate(c=Count("user_member")).order_by("c").first()
        ChatMember.objects.bulk_create([
            ChatMember(is_creator=True, chat_room=ticket,
                       user=creator),
            ChatMember(is_creator=False, chat_room=ticket,
                       user=staff),
        ])
        return ticket

    def create_group(self, name: str, creator: UserModel, members: list, type: str) -> ChatRoomObject:
        """
        create group for a single or several user
        creator: request.user
        members: [<ChatUser: user1>, <ChatUser: user2>, ...]
        type: PUBLIC_GROUPE or PRIVATE_GROUPE
        """
        group = super().create(name=name, type=type)
        # create members
        all_members = [ChatMember(is_creator=True,
                                  is_admin=False,
                                  chat_room=group,
                                  user=creator,
                                  action_permission=creator_permissions())] + \
            [ChatMember(is_creator=False,
                        chat_room=group,
                        user=member)
             for member in members if member.id != creator.id]
        ChatMember.objects.bulk_create(all_members)
        return group


class ChatRoom(RootModel):
    """
    class model for chat room
    """

    def __init__(self, *args, **kwargs) -> None:
        self._member = None
        super().__init__(*args, **kwargs)

    TICKET_PRIORITY = (
        ("LOW", "LOW"),
        ("MEDIUM", "MEDIUM"),
        ("HIGH", "HIGH"),
    )

    CHATROOM_TYPE = (
        ("USER_TICKET", "USER_TICKET"),
        ("PUBLIC_GROUPE", "PUBLIC_GROUPE"),
        ("PRIVATE_GROUPE", "PRIVATE_GROUPE"),
        ("PRIVATE_CHAT", "PRIVATE_CHAT"),
    )

    id = HashidAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')
    photo = models.ImageField(upload_to='group_picture', null=True)
    name = models.CharField(max_length=32)
    closed = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True)
    priority = models.CharField(
        max_length=6, choices=TICKET_PRIORITY, default=None, null=True)
    type = models.CharField(
        max_length=14, choices=CHATROOM_TYPE, default="USER_TICKET")
    read_only = models.BooleanField(default=False)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, through='ChatMember')

    objects = ChatRoomManager()

    @property
    def is_ticket(self) -> bool:
        """
        check if chat room is ticket or not
        """
        if self.type == 'USER_TICKET':
            return True
        return False

    @property
    def is_group(self) -> bool:
        """
        check if chat room is group or not
        """
        if self.type in ['PUBLIC_GROUPE', 'PRIVATE_GROUPE']:
            return True
        return False

    @property
    def is_public_group(self) -> bool:
        """
        check if chat room is public group or not
        """
        if self.type == 'PUBLIC_GROUPE':
            return True
        return False

    @property
    def is_private_group(self) -> bool:
        """
        check if chat room is private group or not
        """
        if self.type == 'PRIVATE_GROUPE':
            return True
        return False

    @property
    def is_private_chat(self) -> bool:
        """
        check if chat room is private group or not
        """
        if self.type == 'PRIVATE_CHAT':
            return True
        return False

    @cached_property
    def all_members(self) -> list:
        """
        return list of all chat room users
        """
        query_set = self.chat_member.select_related("user")
        for member in query_set:
            member.user.role = member.role
            member.user.action_permission = member.action_permission
        all_users = [member.user for member in query_set]
        return all_users

    @property
    def some_members(self) -> list:
        """
        return some chat room users
        """
        if self.is_private_chat or self.is_ticket:
            _some_users = self.all_members
        elif self.is_group:
            _some_users = self.all_members[:10]
        return _some_users

    @property
    def member(self) -> ChatMemberObject:
        """
        return selected member
        """
        return self._member

    def select_member(self, user_id: int) -> bool:
        """
        select a member
        """
        try:
            self._member = self.chat_member.get(
                chat_room_id=self.id,
                user_id=user_id)
            return True
        except ChatMember.DoesNotExist:
            return False

    @property
    def admins(self) -> list:
        """
        return list of chat room admins
        """
        _admins = list(filter(lambda user: user.role ==
                              "admin", self.all_members))
        return _admins

    @property
    def admins_can_update(self) -> list:
        """
        return list of group admins who can update group
        """
        _admins = list(filter(
            lambda user: user.role == "admin" and
            user.has_action_permission("update_group"),
            self.all_members))
        return _admins

    @property
    def admins_can_close(self) -> list:
        """
        return list of group admins who can close group
        """
        _admins = list(filter(
            lambda user: user.role == "admin" and
            user.has_action_permission("close_group"),
            self.all_members))
        return _admins

    @property
    def admins_can_lock(self) -> list:
        """
        return list of group admins who can lock group
        """
        _admins = list(filter(
            lambda user: user.role == "admin" and
            user.has_action_permission("lock_group"),
            self.all_members))
        return _admins

    @property
    def admins_can_add(self) -> list:
        """
        return list of group admins who can add member
        """
        _admins = list(filter(
            lambda user: user.role == "admin" and
            user.has_action_permission("add_member"),
            self.all_members))
        return _admins

    @property
    def admins_can_remove(self) -> list:
        """
        return list of group admins who can remove member
        """
        _admins = list(filter(
            lambda user: user.role == "admin" and
            user.has_action_permission("remove_member"),
            self.all_members))
        return _admins

    @property
    def creator(self) -> UserModel:
        """
        return creator of chat room
        """
        _creator = list(filter(lambda user: user.role ==
                               "creator", self.all_members))[0]
        return _creator

    @property
    def count_members(self) -> int:
        """
        return number of chat room users
        """
        return len(self.all_members)

    def has_member(self, user: UserModel) -> bool:
        """
        check if a user is chat room member or not
        """
        return user in self.all_members

    def has_admin(self, user: UserModel) -> bool:
        """
        check if a user is chat room admin or not
        """
        return user in self.admins

    def lock(self) -> None:
        """
        change chat room read only status
        """
        if self.read_only:
            self.read_only = False
        else:
            self.read_only = True
        self.save()

    def close(self) -> None:
        """
        close chat room
        """
        self.closed = True
        self.save()

    def close_lock(self) -> None:
        """
        close and lock chat room
        """
        self.closed = True
        self.read_only = True
        self.save()

    def close_lock_delete(self) -> None:
        """
        close and delete chat room and make it read only
        """
        self.closed = True
        self.read_only = True
        self.is_deleted = True
        self.save()

    def open(self) -> None:
        """
        open chat room
        """
        self.closed = False
        self.read_only = False
        self.closed_at = None
        self.save()

    def join_public_group(self, user: UserModel) -> bool:
        """
        user joins to a public group if it is not removed
        update ChatMember if user has left the group else create new
        """
        if self.is_public_group and not self.has_member(user):
            try:
                self.chat_member(manager='non_removed_objects').update_or_create(
                    chat_room_id=self.id,
                    user=user,
                    is_deleted=True,
                    defaults={'is_deleted': False}
                )
                return True
            except ChatMember.DoesNotExist:
                return False
        return False

    def add_new_member(self, user: UserModel) -> bool:
        """
        add new member to chat room if it is not removed
        update ChatMember if user has left the chat room else create new
        """
        if not self.has_member(user):
            if self.is_ticket:
                _manager = 'base_objects'
            elif self.is_group:
                _manager = 'non_removed_objects'
            try:
                self.chat_member(manager=_manager).update_or_create(
                    chat_room_id=self.id,
                    user=user,
                    is_deleted=True,
                    defaults={'is_deleted': False}
                )
                return True
            except ChatMember.DoesNotExist:
                return False
        return False

    def remove_member(self, member: UserModel) -> bool:
        """
        removes member from chat room
        """
        if self.has_member(member):
            self.chat_member.filter(
                chat_room_id=self.id,
                user=member
            ).update(is_deleted=True, action_permission=no_permission())
            return True
        return False

    def promote_member(self, member: UserModel) -> bool:
        """
        promote a member to admin level 
        """
        if self.has_member(member):
            self.chat_member.filter(
                chat_room_id=self.id,
                user=member
            ).update(is_admin=True, action_permission=admin_permissions())
            return True
        return False

    def demote_admin(self, admin: UserModel) -> bool:
        """
        demote a admin to member level 
        """
        if self.has_admin(admin):
            self.chat_member.filter(
                chat_room_id=self.id,
                user=admin
            ).update(is_admin=False, action_permission=member_permissions())
            return True
        return False

    def chat_messages(self) -> QuerySet:
        """
        return queryset of chat room messages
        """
        return self.chat_room_message.prefetch_related('file', 'mentions', 'reply_to').order_by('created_at')

    def count_until_last_seen(self, user: UserModel) -> int:
        """
        count user seen messages to find offset for message list
        """
        first_not_seen = self.chat_messages().filter(
            Q(seen=False) & ~Q(sender=user))[:1]
        count = self.chat_messages() \
            .filter(created_at__lt=Subquery(first_not_seen.values('created_at'))).count()
        if count == 0:
            count = self.chat_messages().count() - 1
        return count

    def save(self, *args, **kwargs) -> None:
        if self.closed_at and (self.is_ticket or self.is_group):
            """
            save nothing for closed chat room of type ticket or group
            """
            self.closed = True
            return None

        if self.closed:
            """
            record close time
            """
            self.closed_at = timezone.now()

        return super().save(*args, **kwargs)

    class Meta:
        db_table = 'chat_rooms'


class NonRemovedMemberManager(models.Manager):
    """
    custom manager for chat members who are not removed by admin
    """

    def get_queryset(self):
        return super().get_queryset().\
            annotate(res=F('action_permission') % permission("join_group")).\
            filter(res=0)


class ChatMember(RootModel):
    """
    class model for chat room members
    """
    id = HashidAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')
    is_creator = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    action_permission = models.IntegerField(default=member_permissions())
    chat_room = models.ForeignKey(ChatRoom, related_name=_(
        'chat_member'), on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name=_(
        'user_member'), on_delete=models.CASCADE)

    objects = RootModelManager()
    base_objects = models.Manager()
    non_removed_objects = NonRemovedMemberManager()

    def delete(self, *args, **kwargs) -> tuple:
        if self.is_creator:
            self.chat_room.close_lock_delete()
        self.is_deleted = True
        self.save()
        return tuple()

    @property
    def role(self) -> str:
        """
        user role
        """
        if self.is_creator:
            return "creator"
        elif self.is_admin:
            return "admin"
        return "member"

    class Meta:
        db_table = 'chat_members'
        constraints = [
            models.UniqueConstraint(
                fields=['chat_room', 'user'], name='unique_user_room')
        ]


class FileUpload(RootModel):
    """
    chat file upload
    """

    id = HashidAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name=_(
        'user_upload'), on_delete=models.CASCADE)
    file = models.FileField(upload_to=_('file'))
    file_pic = models.ImageField(upload_to=_('file_picture'), null=True)

    @property
    def size(self) -> int:
        """
        return file size
        """
        return self.file.size

    @property
    def format(self) -> str:
        """
        return file format
        """
        return self.file.name.split(".")[-1].lower()

    @property
    def file_type(self) -> str:
        """
        return file type
        """
        if self.format in IMAGE_FORMATS:
            return 'IMAGE'
        elif self.format in VIDEO_FORMATS:
            return 'VIDEO'
        elif self.format in AUDIO_FORMATS:
            return 'AUDIO'
        else:
            return 'FILE'

    @property
    def name(self) -> str:
        """
        return file name
        """
        return self.file_type + '_' + \
            str(round(time.time())) + '_' + \
            str(random.randrange(10**6, 10**7-1))

    def save(self, *args, **kwargs) -> None:
        self.file.name = self.name + '.' + self.format
        if self.file_pic:
            self.file_pic.name = self.name + '.png'
        return super().save(*args, **kwargs)

    class Meta:
        db_table = 'chat_uploads'


class PredefinedMessage(RootModel):
    """
    class model for predefind message
    """
    id = HashidAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')
    text = models.TextField(null=True)
    file = models.OneToOneField(
        FileUpload, related_name=_('file_predefinedmessage'), on_delete=models.SET_NULL, null=True)

    class Meta:
        db_table = 'predefined_messages'


class Report(RootModel):
    """
    class model for report message
    """
    id = HashidAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')
    message = models.ForeignKey(
        PredefinedMessage, related_name=_('report_message'), on_delete=models.CASCADE)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, related_name=_(
        'reporter'), on_delete=models.DO_NOTHING)
    group = models.ForeignKey(settings.AUTH_USER_MODEL, related_name=_(
        'group'), on_delete=models.DO_NOTHING)

    class Meta:
        db_table = 'reports'
        constraints = [
            models.UniqueConstraint(
                fields=['reporter', 'group'], name='unique_reporter_group')
        ]


class MessageQuerySet(models.query.QuerySet):
    """
    custom QuerySet for Message model
    """

    def seen(self, user: UserModel) -> int:
        """
        user: request.user
        """
        if user.is_staff:
            """
            in case of TICKET, staff user doesn't mark other staff messages as seen 
            """
            return self.filter(seen_at__isnull=True) \
                .exclude(sender__is_staff=True).update(seen=True, seen_at=timezone.now())
        else:
            return self.filter(seen_at__isnull=True) \
                .exclude(sender=user).update(seen=True, seen_at=timezone.now())


class MessageManager(models.manager.BaseManager.from_queryset(MessageQuerySet)):
    """
    custom manager for Message model
    """

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Message(RootModel):
    """
    chat message
    """
    MESSAGE_TYPE = (
        ("TEXT", "TEXT"),
        ("FILE", "FILE"),
        ("ONLINE", "ONLINE"),
        ("NOTICE", "NOTICE"),
        ("TYPING", "TYPING"),
        ("SENDING", "SENDING"),
    )
    id = HashidAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')
    type = models.CharField(max_length=7, choices=MESSAGE_TYPE)
    text = models.TextField(null=True)
    seen = models.BooleanField(default=False)
    file = models.OneToOneField(FileUpload, related_name=_(
        'message_file'), on_delete=models.SET_NULL, null=True)
    member = models.ForeignKey(ChatMember, related_name=_(
        'memeber_message'), on_delete=models.CASCADE)
    reply_to = models.ForeignKey('self', related_name=_(
        'reply_to_message'), on_delete=models.SET_NULL, null=True)
    mentions = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through='Mention', related_name=_('user_mentions'))
    unseen_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through='UnSeen', related_name=_('user_unseen'))

    objects = MessageManager()

    def save(self, *args, **kwargs) -> None:
        if self.type not in ["TEXT", "FILE"]:
            """
            save nothing if it has been seen before
            don't save message unless of type TEXT or FILE 
            """
            return None
        return super().save(*args, **kwargs)

    class Meta:
        db_table = 'chat_messages'


class UnSeen(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.ForeignKey(Message, on_delete=models.CASCADE)

    class Meta:
        db_table = 'unseen'


class Mention(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.ForeignKey(Message, on_delete=models.CASCADE)

    class Meta:
        db_table = 'mentions'


def user_unread_messages(user: UserModel) -> dict:
    """
    send not-seen-messeges event for a user id
    return data format:
    [
        {
            "chat_room": <int>,
            "text": <str, null>,
            "type": <str, null> ["IMAGE","VIDEO","AUDIO","FILE"],
            "created_at": <str> datetime,
            "unread_messages": <int>
        },
        ...
    ]
    """
    # user chat rooms last message
    last_messages = Message.objects.filter(chat_room__chat_member__user=user) \
        .order_by('chat_room', '-created_at') \
        .distinct('chat_room').values('chat_room', 'text', 'type', 'created_at')
    # user chat rooms not seen messages count
    not_seen_messages = Message.objects.filter(~Q(sender=user) & Q(seen=False)).values('chat_room') \
        .annotate(unread_messages=Count('seen'))
    # concat last_messages and not_seen_messages based on chat_room
    for obj in last_messages:
        obj['unread_messages'] = 0
        for msg in not_seen_messages:
            if obj['chat_room'] == msg['chat_room']:
                obj['unread_messages'] = msg['unread_messages']
    return list(last_messages)


@receiver(post_save, sender=Message)
def sse_signal(sender, instance, **kwargs):
    """
    unread message event to chat room members on new message
    send if seen == False (no one in the chat room except sender)
    """
    if not instance.seen:
        members = instance.chat_room.all_members
        for user in members:
            if user:
                send_event('unread_messages_{}'.format(user.id),
                           'message', user_unread_messages(user))
