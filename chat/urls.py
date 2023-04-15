from django.urls import path, include
from rest_framework import routers
from chat.views import (AddMemberToGroupAPIView,
                        BlockUserAPIView, FileUploadView,
                        Un_LockGroupAPIView,
                        CloseGroupAPIView,
                        DemoteAdminAPIView,
                        GroupUpdateAPIView,
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
                        MemberActionPermissionAPIView)


ticket_router = routers.DefaultRouter()
ticket_router.register(r'', TicketViewSet)

provate_chat_router = routers.DefaultRouter()
provate_chat_router.register(r'', PrivateChatViewSet)

group_router = routers.DefaultRouter()
group_router.register(r'', GroupViewSet)

upload_router = routers.DefaultRouter()
upload_router.register(r'', FileUploadView)


urlpatterns = [
    path('ticket/', include(ticket_router.urls)),
    path('ticket/<int:id>/close/', CloseLockTicketAPIView.as_view()),
    path('ticket/<int:id>/assign_staff/', AssignStaffToTicketAPIView.as_view()),

    path('private_chat/', include(provate_chat_router.urls)),
    path('private_chat/<int:id>/block/', BlockUserAPIView.as_view()),
    path('private_chat/<int:id>/unblock/', UnBlockUserAPIView.as_view()),

    path('group/', include(group_router.urls)),
    path('group/<int:id>/update/', GroupUpdateAPIView.as_view()),
    path('group/<int:id>/close/', CloseGroupAPIView.as_view()),
    path('group/<int:id>/lock/', Un_LockGroupAPIView.as_view()),
    path('group/<int:id>/join/', JoinPublicGroupAPIView.as_view()),
    path('group/<int:id>/add/', AddMemberToGroupAPIView.as_view()),
    path('group/<int:id>/remove/', RemoveMemberFromGroupAPIView.as_view()),
    path('group/<int:id>/promote/', PromoteMemberAPIView.as_view()),
    path('group/<int:id>/demote/', DemoteAdminAPIView.as_view()),
    path('group/<int:chat_room_id>/leave/', LeaveGroupAPIView.as_view()),

    path('group/<int:id>/permission/<int:user_id>/', MemberActionPermissionAPIView.as_view()),

    path('upload/', include(upload_router.urls)),
]
