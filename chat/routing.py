from django.conf.urls import url
from .consumers import Consumer, ErrorConsumer


websocket_urlpatterns = [
    url(r'^(?!(ws/chat/(?P<chat_room_id>[^/]+)/)$)', ErrorConsumer.as_asgi()),
    url(r'^ws/chat/(?P<chat_room_id>[^/]+)/$', Consumer.as_asgi()),
]
