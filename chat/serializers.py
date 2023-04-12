from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from chat.models import ChatRoom, UserModel


class MemberSerializer(serializers.ModelSerializer):
    """
    serializer to show chat room members
    """

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
    members = MemberSerializer(
        many=True, read_only=True, source='some_members')

    class Meta:
        model = ChatRoom
        read_only_fields = None
        fields = None


class WritableSingleMemberChatRoomSerializer(serializers.ModelSerializer):
    """
    serilizer to add single member to a chat room
    it is a base class for other serializer to inherit 
    """
    members = MemberSerializer(many=True, source='some_members')

    def is_valid(self, *, raise_exception=False):
        assert hasattr(self, 'initial_data'), (
            'Cannot call `.is_valid()` as no `data=` keyword argument was '
            'passed when instantiating the serializer instance.'
        )

        if not hasattr(self, '_validated_data'):
            try:
                self._validated_data = self.run_validation(self.initial_data)
            except ValidationError as exc:
                self._validated_data = {}
                self._errors = exc.detail
            else:
                self._errors = {}

        if self._errors and raise_exception:
            raise ValidationError(self.errors)

        members = self.initial_data['members']
        # no more than 1 member is allowed
        if len(members) != 1:
            raise ValidationError({"members": "Insert single member."})

        member = members[0]
        if not isinstance(member, dict) or not "username" in member.keys():
            raise ValidationError(
                {"members": "Member should have a valid username field."})

        return not bool(self._errors)

    class Meta:
        model = ChatRoom
        read_only_fields = None
        fields = None


class WritableMultipleMemberChatRoomSerializer(serializers.ModelSerializer):
    """
    serilizer to add multiple members to a chat room
    it is a base serializer for other class to inherit 
    """
    members = MemberSerializer(many=True, source='some_members')

    def is_valid(self, *, raise_exception=False):
        assert hasattr(self, 'initial_data'), (
            'Cannot call `.is_valid()` as no `data=` keyword argument was '
            'passed when instantiating the serializer instance.'
        )

        if not hasattr(self, '_validated_data'):
            try:
                self._validated_data = self.run_validation(self.initial_data)
            except ValidationError as exc:
                self._validated_data = {}
                self._errors = exc.detail
            else:
                self._errors = {}

        if self._errors and raise_exception:
            raise ValidationError(self.errors)

        members = self.initial_data['members']
        # at least 1 member is required
        if len(members) == 0:
            raise ValidationError(
                {"members": "Insert at least single member."})

        for member in members:
            if not isinstance(member, dict) or not "username" in member.keys():
                raise ValidationError(
                    {"members": "Member should have a valid username field."})

        return not bool(self._errors)

    class Meta:
        model = ChatRoom
        read_only_fields = None
        fields = None


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
    TICKET_PRIORITY = (
        ("LOW", "LOW"),
        ("MEDIUM", "MEDIUM"),
        ("HIGH", "HIGH"),
    )
    priority = serializers.ChoiceField(default="LOW", choices=TICKET_PRIORITY)

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


class CloseTicketSerializer(ChatRoomSerializer):
    """
    serializer for close ticket
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
            "members",
            "count_members",
        ]
        fields = read_only_fields


class AssignStaffToTicketSerializer(WritableSingleMemberChatRoomSerializer):
    """
    serializer for staff to assign new staff
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
            "members",
            "count_members",
        ]
        fields = read_only_fields + ["members"]


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
            "closed",
            "read_only",
        ]
        fields = read_only_fields


class PrivateChatSerializer(WritableSingleMemberChatRoomSerializer):
    """
    serializer for private chats
    receive members
    """

    class Meta:
        model = ChatRoom
        read_only_fields = [
            "id",
            "name",
            "closed",
            "read_only",
            "count_members",
        ]
        fields = read_only_fields + ["members"]


class BlockUserSerializer(ChatRoomSerializer):
    """
    read only serializer to block user
    """

    class Meta:
        model = ChatRoom
        read_only_fields = (
            "id",
            "name",
            "closed",
            "members",
            "read_only",
            "count_members",
        )
        fields = read_only_fields


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


class CreateGroupSerializer(WritableMultipleMemberChatRoomSerializer):
    """
    serializer for group creation
    recieve [photo,name,type,members]
    """
    GROUP_TYPE = (
        ("PUBLIC_GROUPE", "PUBLIC_GROUPE"),
        ("PRIVATE_GROUPE", "PRIVATE_GROUPE"),
    )
    type = serializers.ChoiceField(default="PUBLIC_GROUPE", choices=GROUP_TYPE)

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
    GROUP_TYPE = (
        ("PUBLIC_GROUPE", "PUBLIC_GROUPE"),
        ("PRIVATE_GROUPE", "PRIVATE_GROUPE"),
    )
    type = serializers.ChoiceField(default="PUBLIC_GROUPE", choices=GROUP_TYPE)

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


class ReadOnlyGroupSerializer(ChatRoomSerializer):
    """
    serializer to close group
    """

    class Meta:
        model = ChatRoom
        read_only_fields = (
            "id",
            "photo",
            "name",
            "closed",
            "type",
            "read_only",
            "members",
            "count_members",
        )
        fields = read_only_fields


class WritableSingleGroupMemberSerializer(WritableSingleMemberChatRoomSerializer):
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
        fields = read_only_fields + ["members"]
