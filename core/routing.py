from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.sessions import SessionMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application
from django.conf.urls import url
from django.urls import path
from django_eventstream.routing import urlpatterns as sse_urlpatterns
from chat.routing import websocket_urlpatterns
from core.auth import TokenAuthMiddleware


application = ProtocolTypeRouter({
    'websocket':
        AllowedHostsOriginValidator(
            TokenAuthMiddleware(
                URLRouter(
                    websocket_urlpatterns
                )
            )
        ),
    'http':
        URLRouter([
            path('events/<int:user_id>/',
                 SessionMiddlewareStack(
                     AuthMiddlewareStack(URLRouter(sse_urlpatterns))),
                 {'format-channels': ['unread_messages_{user_id}']}),
            url(r'', get_asgi_application()),
        ]
    ),
})
