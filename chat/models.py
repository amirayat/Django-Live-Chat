from functools import lru_cache
from typing import TypeVar
from django.utils import timezone
from django.db import models
from django.db.models import Count, Q
from django.utils.translation import gettext as _
from django.contrib.auth import get_user_model
from core.base_model import RootModel, RootModelManager


UserModel = get_user_model()


ChatRoomObject = TypeVar("ChatRoomObject", bound=models.Model)


class ChatRoomManager(RootModelManager):
    """
    custom manager for chat room
    """

    def update(self, **kwargs):
        """
        update only open chat rooms
        record close time
        """
        if kwargs.get('closed', None):
            return super().update(**kwargs, closed_at=timezone.now())
        return super().update(**kwargs)

    def create(self, creator: UserModel, **kwargs):

        name = kwargs.get('name', str())
        priority = kwargs.get('priority', 'LOW')
        type = kwargs.get('type', 'USER_TICKET')
        contact = kwargs.get('contact', creator)
        members = kwargs.get('members', list())

        if type == 'USER_TICKET':
            return self.create_ticket(name=name, priority=priority, creator=creator)

        elif type == 'PRIVATE_CHAT':
            return self.create_private_chat(creator=creator, contact=contact)

        elif type == 'PUBLIC_GROUPE':
            return self.create_group(name=name, creator=creator, members=members, type=type)

        elif type == 'PRIVATE_GROUPE':
            return self.create_group(name=name, creator=creator, members=members, type=type)

    def create_private_chat(self, creator: UserModel, contact: UserModel) -> ChatRoomObject:
        """
        create private chat for two users
        creator: request.user
        contact: another user 
        """
        name = str(creator.id)+'.'+str(contact.id)+'.'+contact.username
        private_chat, is_create = ChatRoom.objects.get_or_create(
            name=name,
            type="PRIVATE_CHAT"
        )
        if is_create:
            ChatRoomMember.objects.bulk_create([
                ChatRoomMember(is_creator=True, chat_room=private_chat,
                            user=creator),
                ChatRoomMember(is_creator=False, chat_room=private_chat,
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
        ChatRoomMember.objects.bulk_create([
            ChatRoomMember(is_creator=True, chat_room=ticket,
                           user=creator),
            ChatRoomMember(is_creator=False, chat_room=ticket,
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
        all_members = [ChatRoomMember(is_creator=True, is_admin=False, chat_room=group, user=creator)] + \
            [ChatRoomMember(is_creator=False, chat_room=group, user=member)
             for member in members if member.id != creator.id]
        ChatRoomMember.objects.bulk_create(all_members)
        return group


class ChatRoom(RootModel):
    """
    class model for chat room
    """

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

    photo = models.ImageField(upload_to='files', null=True)
    name = models.CharField(max_length=32)
    closed = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True)
    priority = models.CharField(
        max_length=6, choices=TICKET_PRIORITY, default=None, null=True)
    type = models.CharField(
        max_length=14, choices=CHATROOM_TYPE, default="USER_TICKET")
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
        qs = self.chat_room_member.select_related("user")
        for obj in qs:
            obj.user.role = obj.role
        all_users = [obj.user for obj in qs]
        return all_users

    @property
    def some_members(self) -> list:
        """
        return some chat room users
        """
        if self.is_private_chat or self.is_ticket:
            some_users = self.all_members
        elif self.is_group:
            some_users = self.all_members[:10]
        return some_users

    @property
    def admins(self) -> list:
        """
        return list of chat room admins
        """
        admins = list(filter(lambda user: user.role ==
                      "admin", self.all_members))
        return admins

    @property
    def creator(self) -> UserModel:
        """
        return creator of chat room
        """
        creator = list(filter(lambda user: user.role ==
                       "creator", self.all_members))[0]
        return creator

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

    def change_read_only(self) -> None:
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
        close chat room and make it read only
        """
        self.closed = True
        self.read_only = True
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
        user joins to a public group
        update ChatRoomMember if user has left the group else create new
        """
        if self.is_public_group and not self.has_member(user):
            self.chat_room_member(manager='base_objects').update_or_create(
                chat_room_id=self.id,
                user=user,
                is_deleted=True,
                defaults={'is_deleted': False}
            )
            return True
        return False

    def add_new_member(self, user: UserModel) -> bool:
        """
        add new member to chat room
        update ChatRoomMember if user has left the chat room else create new
        """
        if not self.has_member(user):
            self.chat_room_member(manager='base_objects').update_or_create(
                chat_room_id=self.id,
                user=user,
                is_deleted=True,
                defaults={'is_deleted': False}
            )
            return True
        return False

    def remove_member(self, member: UserModel) -> bool:
        """
        removes member from chat room
        """
        if self.has_member(member):
            self.chat_room_member.filter(
                chat_room_id=self.id,
                user=member
            ).update(is_deleted=True)
            return True
        return False

    def leave_chat_room(self, member: UserModel) -> bool:
        """
        user leaves a chat room
        """
        if self.has_member(member):
            self.chat_room_member.filter(
                chat_room_id=self.id,
                user=member
            ).update(is_deleted=True)
            # close the group if user was last member
            if self.count_members == 0:
                self.close()
            return True
        return False

    def promote_member(self, member: UserModel) -> bool:
        """
        promote a member to admin level 
        """
        if self.has_member(member):
            self.chat_room_member.filter(
                chat_room_id=self.id,
                user=member
            ).update(is_admin=True)
            return True
        return False

    def demote_admin(self, admin: UserModel) -> bool:
        """
        demote a admin to member level 
        """
        if self.has_admin(admin):
            self.chat_room_member.filter(
                chat_room_id=self.id,
                user=admin
            ).update(is_admin=False)
            return True
        return False

    def save(self, *args, **kwargs) -> None:

        if self.closed_at and (self.is_ticket or self.is_group):
            """
            update nothing for closed chat room of type ticket or group
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


class ChatRoomMember(RootModel):
    """
    class model for chat room members
    """
    is_creator = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    chat_room = models.ForeignKey(ChatRoom, related_name=_(
        'chat_room_member'), on_delete=models.CASCADE)
    user = models.ForeignKey(UserModel, related_name=_(
        'user_member'), on_delete=models.CASCADE)

    objects = RootModelManager()
    base_objects = models.Manager()

    @property
    def role(self):
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

