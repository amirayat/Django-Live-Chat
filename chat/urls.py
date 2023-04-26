from django.urls import path, include
from rest_framework import routers
from .views import (AddMemberToGroupAPIView,
                    BlockUserAPIView,
                    FileUploadViewSet,
                    LastSeenOffsetAPIView,
                    MessageViewSet,
                    PredefinedMessageViewSet,
                    ReportViewSet,
                    Un_LockGroupAPIView,
                    CloseGroupAPIView,
                    DemoteAdminAPIView,
                    GroupUpdateAPIView,
                    TopPublicGroupViewSet,
                    GroupViewSet,
                    JoinPublicGroupAPIView,
                    LeaveGroupAPIView,
                    PrivateChatViewSet,
                    PromoteMemberAPIView,
                    RemoveMemberFromGroupAPIView,
                    TicketViewSet,
                    CloseLockTicketAPIView,
                    AssignStaffToTicketAPIView,
                    UnBlockUserAPIView,
                    MemberActionPermissionAPIView,
                    UserChatRoomsAPIView)


ticket_router = routers.DefaultRouter()
ticket_router.register(r'', TicketViewSet)

private_chat_router = routers.DefaultRouter()
private_chat_router.register(r'', PrivateChatViewSet)

group_router = routers.DefaultRouter()
group_router.register(r'', GroupViewSet)

upload_router = routers.DefaultRouter()
upload_router.register(r'', FileUploadViewSet)

predefined_messages_router = routers.DefaultRouter()
predefined_messages_router.register(r'', PredefinedMessageViewSet)

report_router = routers.DefaultRouter()
report_router.register(r'', ReportViewSet)

message_router = routers.DefaultRouter()
message_router.register(r'', MessageViewSet)


urlpatterns = [
    path('ticket/<str:id>/close/', CloseLockTicketAPIView.as_view()),
    path('ticket/<str:id>/assign_staff/', AssignStaffToTicketAPIView.as_view()),
    path('ticket/', include(ticket_router.urls)),

    path('private_chat/<str:id>/block/', BlockUserAPIView.as_view()),
    path('private_chat/<str:id>/unblock/', UnBlockUserAPIView.as_view()),
    path('private_chat/', include(private_chat_router.urls)),

    path('group/top/', TopPublicGroupViewSet.as_view()),
    path('group/<str:id>/update/', GroupUpdateAPIView.as_view()),
    path('group/<str:id>/close/', CloseGroupAPIView.as_view()),
    path('group/<str:id>/lock/', Un_LockGroupAPIView.as_view()),
    path('group/<str:id>/join/', JoinPublicGroupAPIView.as_view()),
    path('group/<str:id>/add/', AddMemberToGroupAPIView.as_view()),
    path('group/<str:id>/remove/', RemoveMemberFromGroupAPIView.as_view()),
    path('group/<str:id>/promote/', PromoteMemberAPIView.as_view()),
    path('group/<str:id>/demote/', DemoteAdminAPIView.as_view()),
    path('group/<str:chat_room_id>/leave/', LeaveGroupAPIView.as_view()),
    path('group/', include(group_router.urls)),

    path('chat_rooms/', UserChatRoomsAPIView.as_view()),

    path('group/<str:id>/permission/<str:user_id>/',
         MemberActionPermissionAPIView.as_view()),

    path('predefined_message/', include(predefined_messages_router.urls)),

    path('report/', include(report_router.urls)),

    path('upload/', include(upload_router.urls)),

    path('<str:id>/messages/',
         include(message_router.urls), name="message_list"),

    path('<str:id>/offset/', LastSeenOffsetAPIView.as_view()),
]
