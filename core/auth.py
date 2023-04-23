from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from channels.auth import AuthMiddlewareStack
from .utils import get_user_async



class TokenAuthMiddleware(BaseMiddleware):
    """
    Token query string authorization middleware for Django Channels
    https://www.geeksforgeeks.org/token-authentication-in-django-channels-and-websockets/
    https://github.com/jazzband/djangorestframework-simplejwt/issues/140
    https://stackoverflow.com/questions/43392889/how-do-you-authenticate-a-websocket-with-token-authentication-on-django-channels
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope["query_string"]
        query_params = query_string.decode()
        query_dict = parse_qs(query_params)
        token = query_dict.get("token", [0])[0]

        scope['user'] = await get_user_async(token)
        return await super().__call__(scope, receive, send)


def TokenAuthMiddlewareStack(inner): return TokenAuthMiddleware(
    AuthMiddlewareStack(inner))
