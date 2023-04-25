import ast
import os
import json
import redis
from django.db.models import Q
from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django_eventstream import send_event
from .models import ChatRoom
from .models import Message, unread_messages
from .serializers import MessageContentSerializer
from .serializers import MessageSerializer
from dotenv import load_dotenv


load_dotenv()


DOMAIN = os.getenv('DOMAIN')
REDIS_HOST = os.getenv('REDIS_HOST')
REDIS_PORT = int(os.getenv('REDIS_PORT'))


r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)


def reform_message(msg: dict):
    """
    append url to message file
    """
    if msg['sender']['photo']:
        msg['sender']['photo'] = DOMAIN + msg['sender']['photo']
    if msg.get("file", None):
        file_path = msg["file"].get("file", None)
        file_pic_path = msg["file"].get("file_pic", None)
        # append domain
        if file_path:
            msg["file"]["file"] = DOMAIN + msg["file"]["file"]
        if file_pic_path:
            msg["file"]["file_pic"] = DOMAIN + msg["file"]["file_pic"]
    return msg


class ErrorConsumer(WebsocketConsumer):
    """
    to handle wrong entered routes
    """

    def connect(self):
        print("!"*20, "not valid ws route!")
        return self.close(code=4004)


class Consumer(WebsocketConsumer):
    """
    chat room consumer
    """

    def connect(self):
        self.chat_room_id = self.scope['url_route']['kwargs']['chat_room_id']
        self.chat_room_name = 'chat_room_%s' % self.chat_room_id
        self.user = self.scope['user']

        if not self.user.id:
            """
            reject Anonymouse users connection
            """
            print("!"*20, "reject Anonymouse user!")
            return self.close(code=4004)

        chat_room = ChatRoom.objects.filter(id=self.chat_room_id)

        if not chat_room.exists():
            """
            reject connection for other users
            """
            print("!"*20, "chat room not found!")
            return self.close(code=4004)

        if (not self.user in chat_room.get().members) or (chat_room.get().type == 'TICKET' and not self.user.is_staff):
            """
            allow connect to chat room for members
            allow connect to ticket for staff
            """
            print("!"*20, "not allowed user!")
            return self.close(code=4004)

        async_to_sync(self.channel_layer.group_add)(
            self.chat_room_name,
            self.channel_name
        )

        # store user id in a redis set
        r.sadd(self.chat_room_id, self.user.id)
        self.accept()

        # send list of online users id
        user_online = {
            "type": "user_online",
            "detail": [{"id": item} for item in list(r.smembers(self.chat_room_id))],
        }
        async_to_sync(self.channel_layer.group_send)(
            self.chat_room_name, user_online)

        # seen previous messages
        Message.objects.seen(self.chat_room_id, self.user.id)

    def disconnect(self, close_code):
        # remove user id from online user id list
        user_online = {
            "type": "user_online",
            "detail": [{"id": item} for item in list(r.smembers(self.chat_room_id)) if int(item) != int(self.user.id)],
        }
        async_to_sync(self.channel_layer.group_send)(
            self.chat_room_name, user_online)
        async_to_sync(self.channel_layer.group_discard)(
            self.chat_room_name,
            self.channel_name
        )
        # remove user id from the redis set
        if self.user.id:
            r.srem(self.chat_room_id, self.user.id)

    def receive(self, text_data):
        seen = False
        online_chat_room_members = len(r.smembers(self.chat_room_id))
        if online_chat_room_members > 1:
            seen = True
        text_data_json = json.loads(text_data)
        message_serializer = MessageContentSerializer(data=text_data_json)
        if message_serializer.is_valid():
            if message_serializer.validated_data["type"] == "chat_message":
                message_ins = Message.objects.create(
                    text=message_serializer.validated_data["text"],
                    file_id=message_serializer.validated_data["file"],
                    chat_room_id=self.chat_room_id,
                    sender_id=self.user.id,
                    seen=seen
                )
                text_data_json = reform_message(
                    MessageSerializer(message_ins).data)
                text_data_json['type']= 'chat_message'
            elif message_serializer.validated_data["type"] == "user_typing":
                """
                user typing message from client app 
                """
                text_data_json['type']= 'user_typing'
            async_to_sync(self.channel_layer.group_send)(
                self.chat_room_name, text_data_json)
        else:
            user_notice = {
                "type": "user_notice",
                "detail": [message_serializer.errors],
             }
            self.send(ast.literal_eval(json.dumps(user_notice)))

    def chat_message(self, event):
        print(">"*20, event)
        self.send(text_data=json.dumps(event))

    def user_online(self, event):
        print("O"*20, event)
        self.send(text_data=json.dumps(event))

    def user_typing(self, event):
        print("T"*20, event)
        self.send(text_data=json.dumps(event))
