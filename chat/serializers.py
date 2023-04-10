from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from users.serializers import MemberSerializer
from chat.models import ChatRoom
from core.utils import fields


class ChatRoomSerializer(serializers.ModelSerializer):
    """
    base serializer for chat rooms  
    """
    members = MemberSerializer(many=True, read_only=True, source='some_members')
    class Meta:
        model = ChatRoom
        fields = fields(model)+['members']


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
    priority = serializers.ChoiceField(default="LOW",choices=TICKET_PRIORITY)

    class Meta:
        model = ChatRoom
        fields = (
            "id",
            "name",
            "closed",
            "closed_at",
            "priority",
            "read_only",
            "members",
        )
        read_only_fields = (
            "id",
            "closed",
            "closed_at",
            "read_only"
        )


class CloseTicketSerializer(ChatRoomSerializer):
    """
    serializer for close ticket
    """

    class Meta:
        model = ChatRoom
        fields = (
            "id",
            "name",
            "closed",
            "closed_at",
            "priority",
            "read_only",
            "members",
        )
        read_only_fields = (
            "id",
            "name",
            "closed",
            "closed_at",
            "priority",
            "read_only",
            "members",
        )

class AssignStaffToTicketSerializer(serializers.ModelSerializer):
    """
    serializer for staff to assign new staff
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
        if len(members) != 1:
            raise ValidationError({"members":"Insert single staff."})
        member = members[0]
        if not isinstance(member, dict) or not "username" in member.keys():
            raise ValidationError({"members":"should contain item with valid 'username' field."})

        return not bool(self._errors)

    class Meta:
        model = ChatRoom
        fields = (
            "id",
            "name",
            "closed",
            "closed_at",
            "priority",
            "read_only",
            "members",
        )
        read_only_fields = (
            "id",
            "name",
            "closed",
            "closed_at",
            "priority",
            "read_only",
        )