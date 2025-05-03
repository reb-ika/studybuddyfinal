from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    GroupViewSet,
    ChatMessageViewSet,
    ResourceViewSet,
    SessionViewSet,
    GroupSessionView,
    NotificationSettingsViewSet,  # Added missing import
)

router = DefaultRouter()
router.register(r'groups', GroupViewSet, basename='group')
router.register(r'chats', ChatMessageViewSet, basename='chatmessage')
router.register(r'resources', ResourceViewSet, basename='resource')
router.register(r'sessions', SessionViewSet, basename='session')
router.register(r'notification-settings', NotificationSettingsViewSet, basename='notifications')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('groups/<int:group_id>/sessions/', GroupSessionView.as_view(), name='group-sessions'),
    path('', include(router.urls)),
]