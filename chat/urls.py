from django.urls import path, include
from rest_framework import routers
from chat.views import ChatRoomMessageView, UnreadMessages


chat_room_router = routers.DefaultRouter()
chat_room_router.register(r'', TicketViewSet)

predefind_message_router = routers.DefaultRouter()
predefind_message_router.register(r'', PredefindMessageViewSet)

urlpatterns = [
    path('chatroom/<int:chat_room_id>/messages/', ChatRoomMessageView.as_view()),
    path('chatroom/', include(chat_room_router.urls)),
    path('message/predefind/', include(predefind_message_router.urls)),
    path('message/unread/', UnreadMessages.as_view()),
]
