from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers
from profanity_filter import ProfanityFilter
from chat.permissions import permission_coefficients
from chat.utils import IMAGE_FORMATS, VIDEO_FORMATS, generate_file_pic
from chat.models import (ChatRoom,
                         ChatMember,
                         FileUpload,
                         PredefinedMessage, 
                         Report,
                         Message)


UserModel = get_user_model()


class UserMemberSerializer(serializers.ModelSerializer):
    """
    serializer to show chat room members
    """

    username = serializers.CharField(required=True)

    class Meta:
        model = UserModel
        read_only_fields = [
            "id",
            "username",
            "photo",
            "last_login",
            "role"
        ]
        fields = read_only_fields


class ChatRoomSerializer(serializers.ModelSerializer):
    """
    serializer for chat room with read only members
    it is a base class for other serializer to inherit 
    """
    members = UserMemberSerializer(
        many=True, read_only=True, source='some_members')

    class Meta:
        model = ChatRoom
        read_only_fields = ["id", "members"]
        fields = read_only_fields


class ChatRoomSingleMemberSerializer(serializers.ModelSerializer):
    """
    serilizer to add single member to a chat room
    it is a base class for other serializer to inherit 
    """
    member = UserMemberSerializer(source='some_members')

    class Meta:
        model = ChatRoom
        read_only_fields = ["id"]
        fields = read_only_fields + ["member"]


class AddNewMemberToChatRoomSerializer(ChatRoomSingleMemberSerializer):
    """
    serializer for staff to assign new staff
    """

    class Meta:
        model = ChatRoom
        read_only_fields = [
            "id",
            "name",
            "read_only",
            "count_members",
        ]
        fields = read_only_fields + ["member"]


class ChatRoomMultiMemberSerializer(serializers.ModelSerializer):
    """
    serilizer to add multiple members to a chat room
    it is a base serializer for other class to inherit 
    """
    members = UserMemberSerializer(many=True, source='some_members')

    def validate_members(self, value):
        if len(self.initial_data['members']) == 0:
            raise serializers.ValidationError(
                "At least one member is required.")
        return value

    class Meta:
        model = ChatRoom
        read_only_fields = ["id"]
        fields = read_only_fields + ["members"]


###
# USER_TICKET
###
class ListTicketSerializer(serializers.ModelSerializer):
    """
    serializer for list tickets
    """

    class Meta:
        model = ChatRoom
        read_only_fields = [
            "id",
            "name",
            "closed",
            "closed_at",
            "priority",
            "read_only",
        ]
        fields = read_only_fields


class TicketSerializer(ChatRoomSerializer):
    """
    serializer for tickets
    recieve [name,priority] from creator
    """
    ticket_priority = (
        ("LOW", "LOW"),
        ("MEDIUM", "MEDIUM"),
        ("HIGH", "HIGH"),
    )
    priority = serializers.ChoiceField(default="LOW", choices=ticket_priority)

    class Meta:
        model = ChatRoom
        read_only_fields = [
            "id",
            "closed",
            "closed_at",
            "read_only",
            "members",
            "count_members",
        ]
        fields = read_only_fields + ["name", "priority"]


###
# PRIVATE_CHAT
###
class ListPrivateChatSerializer(serializers.ModelSerializer):
    """
    serializer for list private chats
    """

    class Meta:
        model = ChatRoom
        read_only_fields = [
            "id",
            "name",
            "read_only",
        ]
        fields = read_only_fields


class PrivateChatSerializer(ChatRoomMultiMemberSerializer):
    """
    serializer for private chats
    receive members
    """

    class Meta:
        model = ChatRoom
        read_only_fields = [
            "id",
            "name",
            "read_only",
            "count_members",
        ]
        fields = read_only_fields + ["members"]


###
# GROUPE
###
class ListGroupSerializer(serializers.ModelSerializer):
    """
    serializer for list groups
    """

    class Meta:
        model = ChatRoom
        read_only_fields = [
            "id",
            "photo",
            "name",
            "closed",
            "type",
            "read_only",
        ]
        fields = read_only_fields


class CreateGroupSerializer(ChatRoomMultiMemberSerializer):
    """
    serializer for group creation
    recieve [photo,name,type,members]
    """
    group_type = (
        ("PUBLIC_GROUPE", "PUBLIC_GROUPE"),
        ("PRIVATE_GROUPE", "PRIVATE_GROUPE"),
    )
    type = serializers.ChoiceField(default="PUBLIC_GROUPE", choices=group_type)

    class Meta:
        model = ChatRoom
        read_only_fields = [
            "id",
            "closed",
            "read_only",
            "count_members",
        ]
        fields = read_only_fields + [
            "photo",
            "name",
            "type",
            "members",
        ]


class UpdateGroupSerializer(ChatRoomSerializer):
    """
    serializer to update group
    updatable fields: photo, name, type  
    """
    group_type = (
        ("PUBLIC_GROUPE", "PUBLIC_GROUPE"),
        ("PRIVATE_GROUPE", "PRIVATE_GROUPE"),
    )
    type = serializers.ChoiceField(default="PUBLIC_GROUPE", choices=group_type)

    class Meta:
        model = ChatRoom
        read_only_fileds = [
            "id",
            "closed",
            "read_only",
            "members",
            "count_members",
        ]
        fields = read_only_fileds + [
            "photo",
            "name",
            "type",
        ]


class GroupSingleMemberSerializer(ChatRoomSingleMemberSerializer):
    """
    serializer to add new member to group
    recieve single member
    """

    class Meta:
        model = ChatRoom
        read_only_fields = [
            "id",
            "photo",
            "name",
            "closed",
            "type",
            "read_only",
            "count_members",
        ]
        fields = read_only_fields + ["member"]


class AdminActionPermissionSerializer(serializers.ModelSerializer):
    """
    serilizer to read action permission of a chat room admin
    """

    # admin actions
    update_group = serializers.SerializerMethodField()
    close_group = serializers.SerializerMethodField()
    lock_group = serializers.SerializerMethodField()
    add_member = serializers.SerializerMethodField()
    remove_member = serializers.SerializerMethodField()

    # member actions
    join_group = serializers.SerializerMethodField()
    send_message = serializers.SerializerMethodField()

    def is_valid(self, *, raise_exception=False):
        required_fields = set(self.get_fields().keys()) - \
            {"role", "action_permission"}
        entered_fields = set(self.initial_data.keys()) - \
            {"role", "action_permission"}
        if not required_fields.issubset(entered_fields):
            raise serializers.ValidationError(
                f"required fields: {required_fields-entered_fields}")
        for field, value in self.initial_data.items():
            if field in required_fields and not isinstance(value, bool):
                raise serializers.ValidationError(
                    "Only Boolean type is allowed.")
        return super().is_valid(raise_exception=raise_exception)

    def get_update_group(self, object):
        return object.action_permission % permission_coefficients["update_group"] == 0

    def get_close_group(self, object):
        return object.action_permission % permission_coefficients["close_group"] == 0

    def get_lock_group(self, object):
        return object.action_permission % permission_coefficients["lock_group"] == 0

    def get_add_member(self, object):
        return object.action_permission % permission_coefficients["add_member"] == 0

    def get_remove_member(self, object):
        return object.action_permission % permission_coefficients["remove_member"] == 0

    def get_join_group(self, object):
        return object.action_permission % permission_coefficients["join_group"] == 0

    def get_send_message(self, object):
        return object.action_permission % permission_coefficients["send_message"] == 0

    class Meta:
        model = ChatMember
        read_only_fields = [
            "role",
            "update_group",
            "close_group",
            "lock_group",
            "add_member",
            "remove_member",
            "join_group",
            "send_message",
        ]
        fields = read_only_fields


class MemberActionPermissionSerializer(AdminActionPermissionSerializer):
    """
    serilizer to read action permission of a chat room member
    """

    class Meta:
        model = ChatMember
        read_only_fields = [
            "role",
            "join_group",
            "send_message",
        ]
        fields = read_only_fields


class AdminSerializer(serializers.ModelSerializer):
    """
    serializer for chat member with all action permissions
    """
    permission = AdminActionPermissionSerializer(source='member')

    def validate_permission(self, value):
        permission_serializer = AdminActionPermissionSerializer(
            data=self.initial_data['permission'])
        permission_serializer.is_valid(raise_exception=True)
        return value

    class Meta:
        model = ChatRoom
        fields = [
            "permission"
        ]


class MemberSerializer(serializers.ModelSerializer):
    """
    serializer for chat member with all action permissions
    """
    permission = MemberActionPermissionSerializer(source='member')

    def validate_permission(self, value):
        permission_serializer = MemberActionPermissionSerializer(
            data=self.initial_data['permission'])
        permission_serializer.is_valid(raise_exception=True)
        return value

    class Meta:
        model = ChatRoom
        fields = [
            "permission"
        ]


class UploadSerializer(serializers.ModelSerializer):
    """
    serializer class to upload a file
    uses request.user as the resource owner
    """

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    def validate(self, attrs):
        _file = attrs.get("file")
        _size = _file.size
        if _size > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
            raise serializers.ValidationError(
                {'file': 'File size exceeds the limite.'})
        return super().validate(attrs)

    def create(self, validated_data):
        _file = validated_data.get('file')
        _format = _file.name.split(".")[-1]
        if _format in IMAGE_FORMATS+VIDEO_FORMATS:
            validated_data['file_pic'] = generate_file_pic(_file)
        return super().create(validated_data)

    class Meta:
        model = FileUpload
        read_only_fields = [
            "id",
            "size"
        ]
        fields = read_only_fields + [
            "file",
            "file_pic",
            "file_type",
            "user"
        ]


###
# Predefined Message
###
class PredefinedMessageSerializer(serializers.ModelSerializer):
    """
    serializer class for predefined messages
    """

    def validate(self, attrs):
        text = attrs.get("text")
        file = attrs.get("file")
        if isinstance(text, str) and text.replace(" ","") in ['""', "''"]:
            raise serializers.ValidationError({'text': 'Empty text is not allowed.'})
        if text == file == None:
            raise serializers.ValidationError('Message with no content is not valid.')
        return super().validate(attrs)

    class Meta:
        model = PredefinedMessage
        read_only_fields = [
            "id",
        ]
        fields = read_only_fields + [
            "text",
            "file"
        ]


###
# Report
###
class ReportSerializer(serializers.ModelSerializer):
    """
    serializer class for reports
    """

    class Meta:
        model = Report
        read_only_fields = [
            "id",
            "message",
            "reporter",
            "group"
        ]
        fields = read_only_fields


###
# Message
###
class MessageSerializer(serializers.ModelSerializer):
    """
    serializer for message 
    """

    # sender = UserMemberSerializer(read_only=True)
    file = UploadSerializer(read_only=True, allow_null=True)
    
    def validate(self, attrs):
        type = attrs.get("type")
        text = attrs.get("text", None)
        file = attrs.get("file", None)
        pf = ProfanityFilter()
        if (type == "TEXT" and text is None) or (type == "FILE" and file is None):
            raise serializers.ValidationError({"error":"Message with no content is not valid."})
        if text and not pf.is_clean(text):
            raise serializers.ValidationError({"error":"Message contains swear word."})
        return super().validate(attrs)

    def get_fields(self):
        """
        put a recursive serializer on reply_to
        """
        fields = super().get_fields()
        fields['reply_to'] = MessageSerializer()
        return fields

    class Meta:
        model = Message
        read_only_fields = [
            "id",
            "seen",
            "seen_at",
            "chat_room",
            "sender",
            "created_at"
        ]
        fields = read_only_fields + [
            "type",
            "text",
            "file",
            "reply_to",
        ]
