import time
import random
from typing import TypeVar
from functools import lru_cache
from django.db import models
from django.utils import timezone
from django.db.models import QuerySet, Count, Q, F
from django.utils.translation import gettext as _
from django.contrib.auth import get_user_model
from core.base_model import RootModel, RootModelManager
from chat.permissions import (permission,
                              creator_permissions,
                              admin_permissions,
                              member_permissions,
                              no_permission)
from chat.utils import IMAGE_FORMATS, VIDEO_FORMATS, AUDIO_FORMATS


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

        if type == 'USER_TICKET':
            return self.create_ticket(name=_name, priority=_priority, creator=creator)

        elif type == 'PRIVATE_CHAT':
            return self.create_private_chat(creator=creator, contact=_contact)

        elif type == 'PUBLIC_GROUPE':
            return self.create_group(name=_name, creator=creator, members=_members, type=type)

        elif type == 'PRIVATE_GROUPE':
            return self.create_group(name=_name, creator=creator, members=_members, type=type)

    def create_private_chat(self, creator: UserModel, contact: UserModel) -> ChatRoomObject:
        """
        create private chat for two users
        creator: request.user
        contact: another user 
        """
        _name = str(creator.id)+'.'+creator.username+'_' + \
            str(contact.id)+'.'+contact.username
        _private_chat, _is_create = ChatRoom.objects.get_or_create(
            name=_name,
            type="PRIVATE_CHAT"
        )
        if _is_create:
            ChatMember.objects.bulk_create([
                ChatMember(is_creator=True, chat_room=_private_chat,
                           user=creator),
                ChatMember(is_creator=False, chat_room=_private_chat,
                           user=contact),
            ])
        return _private_chat

    def create_ticket(self, name: str, priority: str, creator: UserModel) -> ChatRoomObject:
        """
        create ticket for request user
        creator: request.user
        """
        _ticket = super().create(name=name, priority=priority, type="USER_TICKET")
        # find staff with less open ticket to assing to the current ticket
        _staff = UserModel.objects.filter(~Q(id=creator.id) & Q(is_staff=True))\
            .annotate(c=Count("user_member")).order_by("c").first()
        ChatMember.objects.bulk_create([
            ChatMember(is_creator=True, chat_room=_ticket,
                       user=creator),
            ChatMember(is_creator=False, chat_room=_ticket,
                       user=_staff),
        ])
        return _ticket

    def create_group(self, name: str, creator: UserModel, members: list, type: str) -> ChatRoomObject:
        """
        create group for a single or several user
        creator: request.user
        members: [<ChatUser: user1>, <ChatUser: user2>, ...]
        type: PUBLIC_GROUPE or PRIVATE_GROUPE
        """
        _group = super().create(name=name, type=type)
        # create members
        _all_members = [ChatMember(is_creator=True,
                                   is_admin=False,
                                   chat_room=_group,
                                   user=creator,
                                   action_permission=creator_permissions())] + \
            [ChatMember(is_creator=False,
                        chat_room=_group,
                        user=member)
             for member in members if member.id != creator.id]
        ChatMember.objects.bulk_create(_all_members)
        return _group


class ChatRoom(RootModel):
    """
    class model for chat room
    """

    def __init__(self, *args, **kwargs) -> None:
        self._member = None
        super().__init__(*args, **kwargs)

    ticket_priority = (
        ("LOW", "LOW"),
        ("MEDIUM", "MEDIUM"),
        ("HIGH", "HIGH"),
    )

    chatroom_type = (
        ("USER_TICKET", "USER_TICKET"),
        ("PUBLIC_GROUPE", "PUBLIC_GROUPE"),
        ("PRIVATE_GROUPE", "PRIVATE_GROUPE"),
        ("PRIVATE_CHAT", "PRIVATE_CHAT"),
    )

    photo = models.ImageField(upload_to='group_picture', null=True)
    name = models.CharField(max_length=32)
    closed = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True)
    priority = models.CharField(
        max_length=6, choices=ticket_priority, default=None, null=True)
    type = models.CharField(
        max_length=14, choices=chatroom_type, default="USER_TICKET")
    read_only = models.BooleanField(default=False)

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

    @property
    @lru_cache(maxsize=None)
    def all_members(self) -> list:
        """
        return list of all chat room users
        """
        _query_set = self.chat_member.select_related("user")
        for obj in _query_set:
            obj.user.role = obj.role
            obj.user.action_permission = obj.action_permission
        _all_users = [obj.user for obj in _query_set]
        return _all_users

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
        except:
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
            except:
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
            except:
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
        return self.chat_room_message.select_related('file', 'reply_to').order_by('-created_at')

    def count_until_last_seen(self, user: UserModel) -> int:
        """
        count user seen messages to find offset for message list
        """
        return self.chat_messages() \
            .filter(Q(seen=False) & ~Q(sender=user)).count()

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
    is_creator = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    action_permission = models.IntegerField(default=221)
    chat_room = models.ForeignKey(ChatRoom, related_name=_(
        'chat_member'), on_delete=models.CASCADE)
    user = models.ForeignKey(UserModel, related_name=_(
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

    user = models.ForeignKey(UserModel, related_name=_(
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
        return self.file.name.split(".")[-1]

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
    text = models.TextField(null=True)
    file = models.OneToOneField(
        FileUpload, related_name=_('file_predefinedmessage'), on_delete=models.SET_NULL, null=True)

    class Meta:
        db_table = 'predefined_messages'


class Report(RootModel):
    """
    class model for report message
    """
    message = models.ForeignKey(
        PredefinedMessage, related_name=_('report_message'), on_delete=models.CASCADE)
    reporter = models.ForeignKey(UserModel, related_name=_(
        'reporter'), on_delete=models.DO_NOTHING)
    group = models.ForeignKey(UserModel, related_name=_(
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
    message_type = (
        ("TEXT", "TEXT"),
        ("FILE", "FILE"),
        ("ONLINE", "ONLINE"),
        ("NOTICE", "NOTICE"),
        ("TYPING", "TYPING"),
        ("SENDING", "SENDING"),
    )
    type = models.CharField(max_length=7, choices=message_type)
    text = models.TextField(null=True)
    seen = models.BooleanField(default=False)
    seen_at = models.DateTimeField(null=True)
    file = models.OneToOneField(FileUpload, related_name=_(
        'message_file'), on_delete=models.CASCADE, null=True)
    chat_room = models.ForeignKey(ChatRoom, related_name=_(
        'chat_room_message'), on_delete=models.CASCADE)
    sender = models.ForeignKey(UserModel, related_name=_(
        'message_sender'), on_delete=models.CASCADE)
    reply_to = models.ForeignKey('self', related_name=_(
        'reply_to_message'), on_delete=models.SET_NULL, null=True)

    objects = MessageManager()

    def save(self, *args, **kwargs) -> None:
        if self.seen_at:
            """
            save nothing if it has been seen before
            """
            return None
        if self.seen:
            """
            record seen time
            """
            self.seen_at = timezone.now()
        return super().save(*args, **kwargs)

    class Meta:
        db_table = 'chat_messages'
