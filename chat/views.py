from functools import lru_cache
from django.http import Http404
from django.contrib.auth import get_user_model
from rest_framework import status, exceptions
from rest_framework.response import Response
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.viewsets import ModelViewSet, GenericViewSet
from rest_framework.permissions import IsAdminUser as IsStaff
from rest_framework.mixins import CreateModelMixin, RetrieveModelMixin, DestroyModelMixin, ListModelMixin
from chat.models import ChatRoom
from chat.serializers import (ListGroupSerializer,
                              ListPrivateChatSerializer,
                              ListTicketSerializer,
                              WritableSingleGroupMemberSerializer,
                              BlockUserSerializer,
                              CreateGroupSerializer,
                              PrivateChatSerializer,
                              ReadOnlyGroupSerializer,
                              TicketSerializer,
                              CloseTicketSerializer,
                              AssignStaffToTicketSerializer,
                              UpdateGroupSerializer)
from chat.permissions import (IsCreator,
                              IsAdmin,
                              IsMember,
                              IsStaffMember,
                              IsMemberWithAction,
                              IsStaffMemberWithAction,
                              IsAuthenticatedNotStaff)


UserModel = get_user_model()


###
# BASE CLASSES FOR OTHER VIEWS
###
class CloseChatRoomAPIView(RetrieveUpdateAPIView):
    """
    close chat room by creator view 
    it is a base class for other views to inherit 
    """
    permission_classes = None
    serializer_class = None
    queryset = ChatRoom.objects.all()
    lookup_field = 'id'
    closed_exception_message = str()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.closed:
            raise exceptions.NotAcceptable(self.closed_exception_message)
        instance.close()
        return Response({"status": "Done"})


class AddNewMemberAPIView(RetrieveUpdateAPIView):
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
        username = serializer.initial_data['members'][0]['username']
        try:
            user = UserModel.objects.get(
                username=username, is_staff=self.is_staff_filter)
        except:
            raise Http404
        # add new member
        result = instance.add_new_member(user)
        if not result:
            raise exceptions.NotAcceptable(
                {"members": "Member already exists."})
        return Response({"status": "Done"})


class MemberManagementAPIView(RetrieveUpdateAPIView):
    """
    view to manage members
    it is a base class for other views to inherit 
    """
    permission_classes = None
    serializer_class = WritableSingleGroupMemberSerializer
    queryset = ChatRoom.objects.filter(
        type__in=['PUBLIC_GROUPE', 'PRIVATE_GROUPE'])
    lookup_field = 'id'
    not_found_message = str()

    @lru_cache(maxsize=None)
    def get_object(self):
        return super().get_object()

    def action(self, *args, **kwargs):
        """
        override view action
        """
        pass

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        username = serializer.initial_data['members'][0]['username']
        try:
            member = UserModel.objects.get(username=username)
        except:
            raise Http404
        # promote member
        result = self.action(member)
        if not result:
            raise exceptions.NotAcceptable({"members": self.not_found_message})
        return Response({"status": "Done"})


###
# USER_TICKET
###
class TicketViewSet(ModelViewSet):
    """
    viewset for ticket 
    """
    permission_classes = [IsCreator | IsStaffMember]
    serializer_class = TicketSerializer
    queryset = ChatRoom.objects.filter(type='USER_TICKET')

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
        return self.queryset.filter(chat_room_member__user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = ChatRoom.objects.create_ticket(
            name=serializer.validated_data['name'],
            priority=serializer.validated_data['priority'],
            creator=request.user)
        headers = self.get_success_headers(serializer.data)
        return Response(self.get_serializer(ticket).data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.closed:
            raise exceptions.NotAcceptable("Ticket has been closed.")
        return super().update(request, *args, **kwargs)


class CloseTicketAPIView(CloseChatRoomAPIView):
    """
    close ticket by creator view 
    """
    permission_classes = [IsCreator]
    serializer_class = CloseTicketSerializer
    queryset = ChatRoom.objects.filter(type='USER_TICKET')
    closed_exception_message = "Ticket has been closed."


class AssignStaffToTicketAPIView(AddNewMemberAPIView):
    """
    assign another staff to ticket by staff
    """
    permission_classes = [IsStaffMemberWithAction]
    serializer_class = AssignStaffToTicketSerializer
    queryset = ChatRoom.objects.filter(type='USER_TICKET')
    closed_exception_message = "Ticket has been closed."
    is_staff_filter = True


###
# PRIVATE_CHAT
###
class PrivateChatViewSet(CreateModelMixin,
                         RetrieveModelMixin,
                         ListModelMixin,
                         GenericViewSet):
    """
    viewset for private chat 
    """
    permission_classes = [IsMember]
    serializer_class = PrivateChatSerializer
    queryset = ChatRoom.objects.filter(type='PRIVATE_CHAT')

    def get_serializer_class(self):
        if self.action == "list":
            self.serializer_class = ListPrivateChatSerializer
        else:
            self.serializer_class = PrivateChatSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        """
        only private chats of request user
        """
        return self.queryset.filter(chat_room_member__user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.initial_data['members'][0]['username']
        try:
            contact = UserModel.objects.get(
                username=username, is_staff=False)
        except:
            raise Http404
        if request.user == contact:
            raise exceptions.NotAcceptable("Self-chat is not allowed.")
        private_chat = ChatRoom.objects.create_private_chat(
            creator=request.user,
            contact=contact)
        headers = self.get_success_headers(serializer.data)
        return Response(self.get_serializer(private_chat).data, status=status.HTTP_201_CREATED, headers=headers)


class BlockUserAPIView(RetrieveUpdateAPIView):
    """
    block user by closing private chat
    """
    permission_classes = [IsMemberWithAction]
    serializer_class = BlockUserSerializer
    queryset = ChatRoom.objects.filter(type='PRIVATE_CHAT')
    lookup_field = 'id'

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # close private chat
        instance.close()
        return Response({"status": "Done"})


class UnBlockUserAPIView(RetrieveUpdateAPIView):
    """
    unblock user by opening private chat
    """
    permission_classes = [IsMemberWithAction]
    serializer_class = BlockUserSerializer
    queryset = ChatRoom.objects.filter(type='PRIVATE_CHAT')
    lookup_field = 'id'

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # open private chat
        instance.open()
        return Response({"status": "Done"})


###
# GROUPE
###
class GroupViewSet(CreateModelMixin,
                   RetrieveModelMixin,
                   ListModelMixin,
                   DestroyModelMixin,
                   GenericViewSet):
    """
    viewset for groups 
    """
    permission_classes = [IsMember]
    serializer_class = CreateGroupSerializer
    queryset = ChatRoom.objects.filter(
        type__in=['PUBLIC_GROUPE', 'PRIVATE_GROUPE'])

    def get_permissions(self):
        if self.action == 'destroy':
            self.permission_classes = [IsCreator | IsStaff]
        if self.action == 'create':
            self.permission_classes = [IsAuthenticatedNotStaff]
        if self.action in ['retrieve', 'list']:
            self.permission_classes = [IsMember]
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
        return self.queryset.filter(chat_room_member__user=self.request.user, chat_room_member__is_deleted=False)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # get members usernames
        usernames = [member['username']
                     for member in serializer.initial_data['members']]
        members = list(UserModel.objects.filter(
            username__in=usernames, is_staff=False))
        ticket = ChatRoom.objects.create_group(
            name=serializer.validated_data['name'],
            creator=request.user,
            members=members,
            type=serializer.validated_data['type'],
        )
        headers = self.get_success_headers(serializer.data)
        return Response(self.get_serializer(ticket).data, status=status.HTTP_201_CREATED, headers=headers)


class GroupUpdateAPIView(RetrieveUpdateAPIView):
    """
    update group view
    """
    permission_classes = [IsAdmin | IsCreator]
    serializer_class = UpdateGroupSerializer
    queryset = ChatRoom.objects.filter(
        type__in=['PUBLIC_GROUPE', 'PRIVATE_GROUPE'])
    lookup_field = 'id'


class CloseGroupAPIView(CloseChatRoomAPIView):
    """
    close group by creator view 
    the group will not accept new member
    """
    permission_classes = [IsAdmin | IsCreator]
    serializer_class = ReadOnlyGroupSerializer
    queryset = ChatRoom.objects.filter(
        type__in=['PUBLIC_GROUPE', 'PRIVATE_GROUPE'])
    closed_exception_message = "Group has been closed."


class Un_LockGroupAPIView(RetrieveUpdateAPIView):
    """
    lock and unlock the group by admin
    no one can send message in group except admin
    """
    permission_classes = [IsAdmin | IsCreator]
    serializer_class = ReadOnlyGroupSerializer
    queryset = ChatRoom.objects.filter(
        type__in=['PUBLIC_GROUPE', 'PRIVATE_GROUPE'])
    lookup_field = 'id'

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # change group read only status
        instance.change_read_only()
        return Response({"status": "Done"})


class JoinPublicGroupAPIView(RetrieveUpdateAPIView):
    """
    join public group view
    """
    permission_classes = [IsAuthenticatedNotStaff]
    serializer_class = ReadOnlyGroupSerializer
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
            raise exceptions.NotAcceptable(
                {"members": "You have already joined this group."})
        return Response({"status": "Done"})


class LeaveGroupAPIView(RetrieveUpdateAPIView):
    """
    user leave group view
    """
    permission_classes = [IsMemberWithAction]
    serializer_class = ReadOnlyGroupSerializer
    queryset = ChatRoom.objects.filter(
        type__in=['PUBLIC_GROUPE', 'PRIVATE_GROUPE'])
    lookup_field = 'id'

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # leave member from group
        result = instance.leave_chat_room(request.user)
        if not result:
            raise exceptions.NotAcceptable({"members": "Member not found."})
        return Response({"status": "Done"})


class AddMemberToGroupAPIView(AddNewMemberAPIView):
    """
    add new member to group by admin
    """
    permission_classes = [IsAdmin | IsCreator]
    serializer_class = WritableSingleGroupMemberSerializer
    queryset = ChatRoom.objects.filter(
        type__in=['PUBLIC_GROUPE', 'PRIVATE_GROUPE'])
    lookup_field = 'id'
    closed_exception_message = "This group no longer accepts new members."
    is_staff_filter = False


class RemoveMemberFromGroupAPIView(RetrieveUpdateAPIView):
    """
    remove a member from group by admin
    """
    permission_classes = [IsAdmin | IsCreator]
    not_found_message = "Member not found."

    def action(self, *args, **kwargs):
        return self.get_object().remove_member(*args, **kwargs)


class PromoteMemberAPIView(MemberManagementAPIView):
    """
    promote member of a group to admin
    """
    permission_classes = [IsCreator]
    not_found_message = "Member not found."

    def action(self, *args, **kwargs):
        return self.get_object().promote_member(*args, **kwargs)


class DemoteAdminAPIView(MemberManagementAPIView):
    """
    demote admin of a group to member
    """
    permission_classes = [IsCreator]
    not_found_message = "Admin not found."

    def action(self, *args, **kwargs):
        return self.get_object().demote_admin(*args, **kwargs)
