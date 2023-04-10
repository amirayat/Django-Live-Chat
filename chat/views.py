from django.http import Http404
from django.contrib.auth import get_user_model
from rest_framework import status, exceptions
from rest_framework.response import Response
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.viewsets import ModelViewSet
from chat.models import ChatRoom
from chat.serializers import TicketSerializer, CloseTicketSerializer, AssignStaffToTicketSerializer
from chat.permissions import IsMemberOrCreator, IsCreator, IsMemberAndStaff


UserModel = get_user_model()


class TicketViewSet(ModelViewSet):
    """
    viewset for ticket 
    """
    permission_classes = [IsMemberOrCreator]
    serializer_class = TicketSerializer
    queryset = ChatRoom.objects.filter(type='USER_TICKET')

    def get_queryset(self):
        """
        only tickets of request user
        """
        return self.queryset.filter(chat_room_member__user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = ChatRoom.objects.create_ticket(
            name=serializer.validated_data['name'],
            priority=serializer.validated_data['priority'],
            creator=self.request.user)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        if instance.closed:
            raise exceptions.NotAcceptable("Ticket has been closed.")
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)


class CloseTicketAPIView(RetrieveUpdateAPIView):
    """
    close ticket by creator view 
    """
    permission_classes = [IsCreator]
    serializer_class = CloseTicketSerializer
    queryset = ChatRoom.objects.filter(type='USER_TICKET')
    lookup_field = 'id'

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        if instance.closed:
            raise exceptions.NotAcceptable("Ticket has been closed!")
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        # close instance
        instance.close()

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)


class AssignStaffToTicketAPIView(RetrieveUpdateAPIView):
    """
    assign another staff to ticket by staff
    """
    permission_classes = [IsMemberAndStaff]
    serializer_class = AssignStaffToTicketSerializer
    queryset = ChatRoom.objects.filter(type='USER_TICKET')
    lookup_field = 'id'

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        if instance.closed:
            raise exceptions.NotAcceptable("Ticket has been closed!")
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # assign another staff
        try:
            staff = UserModel.objects.get(
                username=serializer.initial_data['members'][0]['username'], is_staff=True)
        except:
            raise Http404

        result = instance.add_new_member(staff)
        if not result:
            raise exceptions.NotAcceptable({"members":"Staff already exists on this ticket."})
        

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)