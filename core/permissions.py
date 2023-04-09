from django_eventstream.channelmanager import DefaultChannelManager
from core.utils import get_user_sync


class ChannelManager(DefaultChannelManager):
    """
    sse auth
    """
    global token
    token = None

    def get_channels_for_request(self, request, view_kwargs):
        global token
        token = request.GET.get("token", None)
        return super().get_channels_for_request(request, view_kwargs)

    def can_read_channel(self, user, channel):
        user = get_user_sync(token)
        rcv_user_id = int(channel.split("_")[-1])
        if user and user.id == rcv_user_id:
            return True
        return False