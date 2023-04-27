from functools import lru_cache
from django.conf import settings
from django.http import Http404
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django.db.models import Q, Subquery
from rest_framework import status, exceptions
from rest_framework.response import Response
from rest_framework.generics import RetrieveUpdateAPIView, UpdateAPIView, ListAPIView, RetrieveAPIView
from rest_framework.viewsets import ModelViewSet, GenericViewSet
from rest_framework.permissions import IsAdminUser as IsStaff
from rest_framework.permissions import IsAuthenticated
from rest_framework.mixins import CreateModelMixin, RetrieveModelMixin, UpdateModelMixin, DestroyModelMixin, ListModelMixin
from .models import ChatRoom, ChatMember, FileUpload, PredefinedMessage, Report, Message
from .serializers import (ChatRoomSerializer,
                          ListGroupSerializer,
                          ListPrivateChatSerializer,
                          ListTicketSerializer,
                          GroupSingleMemberSerializer,
                          CreateGroupSerializer,
                          MessageSerializer,
                          PredefinedMessageSerializer,
                          PrivateChatSerializer,
                          ReportSerializer,
                          TicketSerializer,
                          AddNewMemberToChatRoomSerializer,
                          UpdateGroupSerializer,
                          AdminSerializer,
                          MemberPermissionSerializer,
                          UploadSerializer,
                          ListChatRoomsSerializer)
from .permissions import (IsAdmin_CanAdd,
                          IsAdmin_CanClose,
                          IsAdmin_CanLock,
                          IsAdmin_CanRemove,
                          IsAdmin_CanUpdate,
                          IsCreator,
                          IsMember,
                          IsMemberNotStaff,
                          IsAuthenticatedNotStaff, IsMessageSender,
                          permission)


UserModel = get_user_model()


# •••••••••••••••••••••••••••
# BASE CLASSES FOR OTHER VIEWS
# •••••••••••••••••••••••••••
class AddNewMemberAPIView(UpdateAPIView):
    """
    add new member to chat room
    it is a base class for other views to inherit
    """
    permission_classes = None
    serializer_class = None
    queryset = ChatRoom.objects.all()
    lookup_field = 'id'
    closed_exception_message = str()
    is_staff_filter = bool()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        if instance.closed:
            raise exceptions.NotAcceptable(self.closed_exception_message)
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        _username = serializer.validated_data.get('some_members')['username']
        try:
            user = UserModel.objects.get(
                username=_username, is_staff=self.is_staff_filter)
        except UserModel.DoesNotExist:
            raise Http404
        # add new member
        result = instance.add_new_member(user)
        if not result:
            """
            user has removed by admin or already has joined the group
            """
            raise exceptions.NotAcceptable(
                {"member": "User can't rejoin this group."})
        return Response({"status": "Done"})


class MemberManagementAPIView(UpdateAPIView):
    """
    view to manage members
    it is a base class for other views to inherit
    """
    permission_classes = None
    serializer_class = GroupSingleMemberSerializer
    queryset = ChatRoom.objects.filter(
        type__in=['PUBLIC_GROUPE', 'PRIVATE_GROUPE'])
    lookup_field = 'id'
    not_found_message = str()

    @lru_cache(maxsize=None)
    def get_object(self):
        return super().get_object()

    def operation(self, *args, **kwargs):
        """
        override view operation
        """
        pass

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        _username = serializer.validated_data.get('some_members')['username']
        try:
            member = UserModel.objects.get(username=_username)
        except UserModel.DoesNotExist:
            raise Http404
        # promote member
        result = self.operation(member)
        if not result:
            raise exceptions.NotAcceptable({"members": self.not_found_message})
        return Response({"status": "Done"})


class UserChatRoomsAPIView(ListAPIView):
    """
    user list of chat rooms
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ListChatRoomsSerializer
    queryset = ChatRoom.objects.all()

    def get_queryset(self):
        return super().get_queryset().filter(chat_member__user=self.request.user)


# •••••••••••
# USER_TICKET
# •••••••••••
class TicketViewSet(ModelViewSet):
    """
    viewset for ticket
    """
    permission_classes = [IsAuthenticated]
    serializer_class = TicketSerializer
    queryset = ChatRoom.objects.filter(type='USER_TICKET')

    def get_permissions(self):
        if self.action == 'create':
            self.permission_classes = [IsAuthenticated]
        elif self.action in ['destroy', 'update']:
            self.permission_classes = [IsCreator]
        elif self.action in ['retrieve', 'list']:
            self.permission_classes = [IsCreator | (IsMember & IsStaff)]
        return super().get_permissions()

    @lru_cache(maxsize=None)
    def get_object(self):
        return super().get_object()

    def get_serializer_class(self):
        if self.action == "list":
            self.serializer_class = ListTicketSerializer
        else:
            self.serializer_class = TicketSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        """
        only returns tickets of current request user
        """
        return self.queryset.filter(chat_member__user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = ChatRoom.objects.create_ticket(
            name=serializer.validated_data.get('name'),
            priority=serializer.validated_data.get('priority'),
            creator=request.user)
        headers = self.get_success_headers(serializer.data)
        return Response(self.get_serializer(ticket).data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.closed:
            raise exceptions.NotAcceptable("Ticket has been closed.")
        return super().update(request, *args, **kwargs)


class CloseLockTicketAPIView(UpdateAPIView):
    """
    close and lock ticket by creator view
    """
    permission_classes = [IsCreator]
    serializer_class = ChatRoomSerializer
    queryset = ChatRoom.objects.filter(type='USER_TICKET')
    lookup_field = 'id'

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.closed:
            raise exceptions.NotAcceptable("Ticket has been closed.")
        instance.close_lock()
        return Response({"status": "Done"})


class AssignStaffToTicketAPIView(AddNewMemberAPIView):
    """
    assign another staff to ticket by staff
    """
    permission_classes = [IsMember & IsStaff]
    serializer_class = AddNewMemberToChatRoomSerializer
    queryset = ChatRoom.objects.filter(type='USER_TICKET')
    closed_exception_message = "Ticket has been closed."
    is_staff_filter = True


# •••••••••••
# PRIVATE_CHAT
# •••••••••••
class PrivateChatViewSet(CreateModelMixin,
                         RetrieveModelMixin,
                         ListModelMixin,
                         GenericViewSet):
    """
    viewset for private chat
    """
    permission_classes = [IsMemberNotStaff]
    serializer_class = PrivateChatSerializer
    queryset = ChatRoom.objects.filter(type='PRIVATE_CHAT')

    def get_serializer_class(self):
        if self.action == "list":
            self.serializer_class = ListPrivateChatSerializer
        elif self.action == "create":
            self.serializer_class = AddNewMemberToChatRoomSerializer
        else:
            self.serializer_class = PrivateChatSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        """
        only private chats of request user
        """
        return self.queryset.filter(chat_member__user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _username = serializer.validated_data.get('some_members')['username']
        try:
            _contact = UserModel.objects.get(
                username=_username, is_staff=False)
        except UserModel.DoesNotExist:
            raise Http404
        if request.user == _contact:
            raise exceptions.NotAcceptable("Self-chat is not allowed.")
        private_chat = ChatRoom.objects.create_private_chat(
            creator=request.user,
            contact=_contact)
        headers = self.get_success_headers(serializer.data)
        return Response({"status": "Done"})


class BlockUserAPIView(UpdateAPIView):
    """
    block user by closing and locking private chat
    """
    permission_classes = [IsMemberNotStaff]
    serializer_class = ChatRoomSerializer
    queryset = ChatRoom.objects.filter(type='PRIVATE_CHAT')
    lookup_field = 'id'

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # close private chat
        instance.lock()
        return Response({"status": "Done"})


class UnBlockUserAPIView(UpdateAPIView):
    """
    unblock user by opening private chat
    """
    permission_classes = [IsMemberNotStaff]
    serializer_class = ChatRoomSerializer
    queryset = ChatRoom.objects.filter(type='PRIVATE_CHAT')
    lookup_field = 'id'

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # open private chat
        instance.open()
        return Response({"status": "Done"})


# •••••••••••
# GROUPE
# •••••••••••
class TopPublicGroupViewSet(ListAPIView):
    """
    list of top public groups
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ListGroupSerializer
    queryset = ChatRoom.objects.top_public_groups()

    @method_decorator(cache_page(60*60*2))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class GroupViewSet(CreateModelMixin,
                   RetrieveModelMixin,
                   ListModelMixin,
                   DestroyModelMixin,
                   GenericViewSet):
    """
    viewset for groups
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CreateGroupSerializer
    queryset = ChatRoom.objects.filter(
        type__in=['PUBLIC_GROUPE', 'PRIVATE_GROUPE'])

    def get_permissions(self):
        if self.action == 'destroy':
            self.permission_classes = [IsCreator | IsStaff]
        elif self.action == 'create':
            self.permission_classes = [IsAuthenticatedNotStaff]
        elif self.action in ['retrieve', 'list']:
            self.permission_classes = [IsAuthenticated]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "list":
            self.serializer_class = ListGroupSerializer
        else:
            self.serializer_class = CreateGroupSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        """
        only groups which request user has joined
        show all groups to staff
        """
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(chat_member__user=self.request.user, chat_member__is_deleted=False)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # get members usernames
        _usernames = [member['username']
                      for member in serializer.validated_data.get('some_members')]
        _members = list(UserModel.objects.filter(
            username__in=_usernames, is_staff=False))
        ticket = ChatRoom.objects.create_group(
            name=serializer.validated_data.get('name'),
            creator=request.user,
            members=_members,
            type=serializer.validated_data.get('type'),
        )
        headers = self.get_success_headers(serializer.data)
        return Response(self.get_serializer(ticket).data, status=status.HTTP_201_CREATED, headers=headers)


class GroupUpdateAPIView(UpdateAPIView):
    """
    update group view
    """
    permission_classes = [IsAdmin_CanUpdate | IsCreator]
    serializer_class = UpdateGroupSerializer
    queryset = ChatRoom.objects.filter(
        type__in=['PUBLIC_GROUPE', 'PRIVATE_GROUPE'])
    lookup_field = 'id'


class CloseGroupAPIView(UpdateAPIView):
    """
    close group by creator view
    the group will not accept new member
    """
    permission_classes = [IsAdmin_CanClose | IsCreator]
    serializer_class = ChatRoomSerializer
    queryset = ChatRoom.objects.filter(
        type__in=['PUBLIC_GROUPE', 'PRIVATE_GROUPE'])
    lookup_field = 'id'

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.closed:
            raise exceptions.NotAcceptable("Group has been closed.")
        instance.close()
        return Response({"status": "Done"})


class Un_LockGroupAPIView(UpdateAPIView):
    """
    lock and unlock the group by admin
    no one can send message in group except admin
    """
    permission_classes = [IsAdmin_CanLock | IsCreator]
    serializer_class = ChatRoomSerializer
    queryset = ChatRoom.objects.filter(
        type__in=['PUBLIC_GROUPE', 'PRIVATE_GROUPE'])
    lookup_field = 'id'

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # change group read only status
        instance.lock()
        return Response({"status": "Done"})


class JoinPublicGroupAPIView(RetrieveUpdateAPIView):
    """
    join public group view
    """
    permission_classes = [IsAuthenticatedNotStaff]
    serializer_class = ChatRoomSerializer
    queryset = ChatRoom.objects.filter(type='PUBLIC_GROUPE')
    lookup_field = 'id'

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.closed:
            raise exceptions.NotAcceptable(
                {"This group no longer accepts new members."})
        # join member to group
        result = instance.join_public_group(request.user)
        if not result:
            """
            user has removed by admin or already has joined the group
            """
            raise exceptions.NotAcceptable(
                {"members": "You can't rejoin this group."})
        return Response({"status": "Done"})


class LeaveGroupAPIView(UpdateAPIView):
    """
    user leave group view
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ChatRoomSerializer
    queryset = ChatMember.objects.select_related('user')
    lookup_field = 'chat_room_id'

    def get_queryset(self):
        queryset = self.queryset.filter(user=self.request.user)
        return queryset

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({"status": "Done"})


class AddMemberToGroupAPIView(AddNewMemberAPIView):
    """
    add new member to group by admin
    """
    permission_classes = [IsAdmin_CanAdd | IsCreator]
    serializer_class = GroupSingleMemberSerializer
    queryset = ChatRoom.objects.filter(
        type__in=['PUBLIC_GROUPE', 'PRIVATE_GROUPE'])
    lookup_field = 'id'
    closed_exception_message = "This group no longer accepts new members."
    is_staff_filter = False


class RemoveMemberFromGroupAPIView(MemberManagementAPIView):
    """
    remove a member from group by admin
    """
    permission_classes = [IsAdmin_CanRemove | IsCreator]
    not_found_message = "Member not found."

    def operation(self, *args, **kwargs):
        return self.get_object().remove_member(*args, **kwargs)


class PromoteMemberAPIView(MemberManagementAPIView):
    """
    promote member of a group to admin
    """
    permission_classes = [IsCreator]
    not_found_message = "Member not found."

    def operation(self, *args, **kwargs):
        return self.get_object().promote_member(*args, **kwargs)


class DemoteAdminAPIView(MemberManagementAPIView):
    """
    demote admin of a group to member
    """
    permission_classes = [IsCreator]
    not_found_message = "Admin not found."

    def operation(self, *args, **kwargs):
        return self.get_object().demote_admin(*args, **kwargs)


class MemberActionPermissionAPIView(RetrieveUpdateAPIView):
    """
    view for a member with action permissions
    """
    permission_classes = [IsCreator]
    serializer_class = MemberPermissionSerializer
    queryset = ChatRoom.objects.filter(
        type__in=['PUBLIC_GROUPE', 'PRIVATE_GROUPE'])
    lookup_field = 'id'

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.member.role == "member":
            serializer = MemberPermissionSerializer(instance)
        else:
            serializer = AdminSerializer(instance)
        return Response(serializer.data)

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)
        self.check_object_permissions(self.request, obj)
        result = obj.select_member(self.kwargs['user_id'])
        if not result:
            raise Http404
        return obj

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        if instance.member.role == "member":
            serializer = MemberPermissionSerializer(
                instance, data=request.data, partial=partial)
        else:
            serializer = AdminSerializer(
                instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        _permission = [k for k, v in serializer.initial_data.get(
            "permission").items() if v]
        _action_permission = permission(*_permission)
        if _action_permission < permission("add_member"):
            """
            creator downgrades user permissions under than admin level
            """
            ChatMember.objects.filter(chat_room_id=self.kwargs['id'], user_id=self.kwargs['user_id']).\
                update(action_permission=_action_permission, is_admin=False)
        else:
            ChatMember.objects.filter(chat_room_id=self.kwargs['id'], user_id=self.kwargs['user_id']).\
                update(action_permission=_action_permission)
        return Response({"status": "Done"})


# •••••••••••
# FILE UPLOAD
# •••••••••••
class FileUploadViewSet(CreateModelMixin,
                        RetrieveModelMixin,
                        DestroyModelMixin,
                        GenericViewSet):
    """
    user uploads a file
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UploadSerializer
    queryset = FileUpload.objects.all()

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


# •••••••••••
# Predefined Message
# •••••••••••
class PredefinedMessageViewSet(ModelViewSet):
    """
    viewset for predefined messages
    """
    permission_classes = [IsStaff]
    serializer_class = PredefinedMessageSerializer
    queryset = PredefinedMessage.objects.all()

    @method_decorator(cache_page(60*60*168))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


# •••••••••••
# Report
# •••••••••••
class ReportViewSet(ModelViewSet):
    """
    viewset for reports
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ReportSerializer
    queryset = Report.objects.all()

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(reporter=self.request.user)

    def get_permissions(self):
        if self.action in ['retrieve', 'create', 'destroy', 'update']:
            self.permission_classes = [IsAuthenticatedNotStaff]
        elif self.action in ['list']:
            self.permission_classes = [IsStaff]
        return super().get_permissions()

    @method_decorator(cache_page(60*60*2))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


# •••••••••••
# Message
# •••••••••••
class LastSeenOffsetAPIView(RetrieveAPIView):
    """
    to find last seen massage offset for MessageView
    """
    permission_classes = [IsMember]
    serializer_class = None
    queryset = ChatRoom.objects.all()
    lookup_field = 'id'

    def retrieve(self, request, *args, **kwargs):
        limit = int(request.GET.get(
            'limit', settings.REST_FRAMEWORK.get('PAGE_SIZE', '5')))
        chat_room = self.get_object()
        chat_messages = Message.objects.filter(member__chat_room=chat_room)
        first_not_seen = chat_messages.filter(
            Q(seen=False) & ~Q(member__user=request.user))[:1]
        count = chat_messages.filter(created_at__lt=Subquery(
            first_not_seen.values('created_at'))).count()
        if count == 0:
            count = chat_messages.count() - 1
        offset = count//limit*limit
        return Response({'limit': limit, 'offset': offset})


class MessageViewSet(ListModelMixin,
                     UpdateModelMixin,
                     DestroyModelMixin,
                     GenericViewSet):
    """
    view class for messages
    """
    permission_classes = [IsMember]
    serializer_class = MessageSerializer
    queryset = Message.objects.all()
    lookup_field = 'id'

    def get_permissions(self):
        if self.action in ['list']:
            self.permission_classes = [IsMember]
        else:
            self.permission_classes = [IsMessageSender]
        return super().get_permissions()

    def list(self, request, *args, **kwargs):
        _id_gte = self.request.GET.get('id_gte', None)
        try:
            chat_room = ChatRoom.objects.get(id=self.kwargs[self.lookup_field])
        except ChatRoom.DoesNotExist:
            raise Http404
        self.check_object_permissions(self.request, chat_room)
        queryset = Message.objects.filter(member__chat_room=chat_room)\
            .prefetch_related('member__user', 'file', 'mentions', 'reply_to').order_by('created_at')
        if _id_gte:
            queryset = queryset.filter(id__gte=_id_gte)
        page = self.paginate_queryset(queryset)

        # seen messages in the page by request user if there is not seen message
        seen_messages = list()
        for i, msg in enumerate(page):
            if not msg.seen:
                msg.seen_message()
                seen_messages.append(i)
                pass

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response_data = serializer.data
            for i, obj in enumerate(response_data):
                if i in seen_messages:
                    obj['seen'] = True
            return self.get_paginated_response(response_data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
