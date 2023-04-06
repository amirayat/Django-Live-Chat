import json
from time import time
from operator import and_
from functools import reduce
from datetime import datetime
from django.db.models import Q
from django.http import Http404
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django_eventstream import send_event
from rest_framework import mixins, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.viewsets import ModelViewSet, GenericViewSet
from rest_framework.exceptions import PermissionDenied, NotAcceptable
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import LimitOffsetPagination
from core.base_view import CustomModelViewSet
from chat.models import *
from chat.serializers import *
from permissions.permissions import *


UserModel = get_user_model()


class ChatRoomMessageView(APIView, LimitOffsetPagination):
    """
    view class to list ticket messages
    """
    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer
    pagination_class = LimitOffsetPagination
    pagination_class.default_limit = settings.MESSAGE_LIMITE
    pagination_class.max_limit = settings.MESSAGE_LIMITE

    def get_queryset(self):
        timerange = {
            "from": self.request.query_params.get('from'),
            "to": self.request.query_params.get('to'),
        }
        for k, v in timerange.copy().items():
            if v:
                if not (v.isdigit() and len(v) == 13):
                    raise NotAcceptable("Invalide timestamp range.")
            else:
                timerange.pop(k)

        chat_room_id = self.kwargs["chat_room_id"]

        Qlist = [
            Q(chat_room_id=chat_room_id),
            Q(created_at__gte=datetime.utcfromtimestamp(
                int(timerange.get("from", 0))/1000)),
            Q(created_at__lte=datetime.utcfromtimestamp(
                int(timerange.get("to", time()*1000))/1000)),
        ]

        if not ChatRoom.objects.get(id=chat_room_id).has_member(self.request.user.id):
            """
            requested user is not member of this chat room
            """
            raise Http404

        return Message.objects.filter(reduce(
            and_, [q for q in Qlist if q.children[0][1] is not None]
        )).order_by("created_at")

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        paginated_queryset = self.paginate_queryset(queryset, request)
        Message.objects.filter(id__in={instance.id for instance in paginated_queryset}).seen(
            self.kwargs["chat_room_id"], self.request.user.id)
        serializer = self.serializer_class(paginated_queryset, many=True)
        if queryset.exists():
            return self.get_paginated_response(serializer.data)
        raise Http404


class TicketViewSet(CustomModelViewSet):
    """
    allow authenticated user to view or edit tickets
    """
    queryset = ChatRoom.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.user.is_superuser:
            return TicketSerializerSuperuser
        elif self.request.user.is_staff:
            return TicketSerializerStaff
        else:
            if self.request.method in SAFE_METHODS:
                return TicketSerializerOwnerSafe
            return TicketSerializerOwnerWritable

    def str2bool(self, parameter):
        if parameter:
            if parameter.lower() == "false":
                return False
            elif parameter.lower() == "true":
                return True

    def get_queryset(self):
        priority = self.request.query_params.get('priority')
        department_id = self.request.query_params.get('department')
        negotiant = self.request.query_params.get('negotiant')
        status = self.request.query_params.get('status')
        Qlist = [
            Q(id__gt=0),
            Q(priority=priority),
            Q(department_id=department_id),
            Q(status=status),
        ]
        if negotiant == "customer":
            Qlist.append(Q(customer__isnull=False))
            Qlist.append(Q(supplier__isnull=True))
        elif negotiant == "supplier":
            Qlist.append(Q(customer__isnull=True))
            Qlist.append(Q(supplier__isnull=False))
        queryset = ChatRoom.objects.filter(reduce(
            and_, [q for q in Qlist if q.children[0][1] is not None]
        )).order_by("-created_at")
        if self.request.user.is_superuser:
            return queryset.all()
        elif self.request.user.is_staff:
            return queryset.filter(Q(staff_id=self.request.user.id) | Q(staff=None))
        elif self.request.user.is_supplier:
            return queryset.filter(supplier_id=self.request.user.id)
        return queryset.filter(customer_id=self.request.user.id)

    def perform_create(self, serializer):
        if self.request.user.is_staff:
            ticket_group_obj = TicketGroup.objects.create()
            serializer.save(
                staff=self.request.user,
                ticket_group=ticket_group_obj
            )
        elif self.request.user.is_supplier:
            ticket_group_obj = TicketGroup.objects.create()
            serializer.save(
                supplier=self.request.user,
                ticket_group=ticket_group_obj
            )
        else:
            max_open_ticket = UserModel.objects.get(
                id=self.request.user.id).max_open_ticket
            open_tickets = ChatRoom.objects.filter(
                Q(customer=self.request.user),
                ~Q(status="CLOSED")
            ).count()
            if open_tickets < max_open_ticket:
                ticket_group_obj = TicketGroup.objects.create()
                serializer.save(
                    customer=self.request.user,
                    ticket_group=ticket_group_obj
                )
            else:
                raise NotAcceptable(
                    {"detail": ["تعداد تیکت های درحال بررسی شما به حد آستانه رسیده است."]})
        data = serializer.data
        Message.objects.create(
            text=data["description"],
            chat_room_id=data["id"],
            sender_id=self.request.user.id
        )
        Message.objects.bulk_create([
            Message(
                file_id=obj["id"],
                chat_room_id=data["id"],
                sender_id=self.request.user.id
            ) for obj in data["ticket_upload"]
        ])

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status == "CLOSED":
            raise NotAcceptable(
                {"detail": ["تیکت بسته شده قابل ویرایش نیست."]})
        return super().update(request, *args, **kwargs)


class PredefindMessageViewSet(CustomModelViewSet):
    """
    allow staff user to view or edit predefind messages
    """
    permission_classes = [IsAdminUser]
    serializer_class = PredefindMessageSerializer
    queryset = PredefindMessage.objects.all()


class UnreadMessages(APIView):
    """
    get unread messages
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        message = unread_messages(request.user.id)
        return Response(message, status=status.HTTP_200_OK)
