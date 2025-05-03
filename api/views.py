from rest_framework import viewsets, generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from django.utils import timezone
from .models import *
from .serializers import *
from rest_framework.decorators import action
import os
from .models import NotificationSettings
from .serializers import NotificationSettingsSerializer

User = get_user_model()

# Auth Views

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        if user:
            refresh = RefreshToken.for_user(user)
            serializer = UserSerializer(user)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': serializer.data
            })
        return Response({'error': 'Invalid credentials'}, status=401)

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data['refresh']
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=205)
        except Exception:
            return Response(status=400)

# Group Views
class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        group = serializer.save(created_by=self.request.user)
        GroupMembership.objects.create(
            user=self.request.user,
            group=group,
            role='admin'
        )

    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        group = self.get_object()
        if group.members.filter(id=request.user.id).exists():
            return Response({'detail': 'Already a member'}, status=400)
        
        GroupMembership.objects.create(
            user=request.user,
            group=group,
            role='member'
        )
        return Response({'status': 'joined group'}, status=200)

    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        group = self.get_object()
        membership = group.groupmembership_set.filter(user=request.user).first()
        if not membership:
            return Response({'detail': 'Not a member'}, status=400)
        
        if membership.role == 'admin' and group.groupmembership_set.filter(role='admin').count() == 1:
            return Response({'detail': 'Cannot leave as the only admin'}, status=400)
        
        membership.delete()
        return Response({'status': 'left group'}, status=200)

# Chat Views
class ChatMessageViewSet(viewsets.ModelViewSet):
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = ChatMessage.objects.all()

    def get_queryset(self):
        group_id = self.request.query_params.get('group_id')
        if group_id:
            group = get_object_or_404(Group, id=group_id)
            if not group.members.filter(id=self.request.user.id).exists():
                raise PermissionDenied("Not a group member")
            return self.queryset.filter(group_id=group_id).order_by('-timestamp')[:50]
        return self.queryset.none()

    def perform_create(self, serializer):
        group = serializer.validated_data['group']
        if not group.members.filter(id=self.request.user.id).exists():
            raise PermissionDenied("Not a group member")
        serializer.save(user=self.request.user)

# Resource Views
class ResourceViewSet(viewsets.ModelViewSet):
    serializer_class = ResourceSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Resource.objects.all()

    def get_queryset(self):
        group_id = self.request.query_params.get('group_id')
        queryset = self.queryset
        if group_id:
            group = get_object_or_404(Group, id=group_id)
            if not group.members.filter(id=self.request.user.id).exists():
                raise PermissionDenied("Not a group member")
            queryset = queryset.filter(group=group)
        return queryset.order_by('-uploaded_at')
     
    def get_queryset(self):
        queryset = super().get_queryset()
        file_type = self.request.query_params.get('type')
        if file_type:
            queryset = queryset.filter(file_type=file_type)
        return queryset
    
    def perform_create(self, serializer):
        group = serializer.validated_data['group']
        if not group.members.filter(id=self.request.user.id).exists():
            raise PermissionDenied("Not a group member")
        serializer.save(uploaded_by=self.request.user)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        resource = self.get_object()
        if not resource.group.members.filter(id=request.user.id).exists():
            raise PermissionDenied("Not authorized")
        
        resource.download_count += 1
        resource.save()
        
        response = FileResponse(resource.file.open(), as_attachment=True)
        response['Content-Disposition'] = f'attachment; filename="{resource.title}.{resource.file_type}"'
        return response

    @action(detail=True, methods=['post'])
    def toggle_favorite(self, request, pk=None):
        resource = self.get_object()
        resource.is_favorite = not resource.is_favorite
        resource.save()
        return Response({'status': 'success', 'is_favorite': resource.is_favorite})

# Session Views
class SessionViewSet(viewsets.ModelViewSet):
    serializer_class = SessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Session.objects.all()

    def get_queryset(self):
        group_id = self.request.query_params.get('group_id')
        status = self.request.query_params.get('status')
        queryset = self.queryset
        
        if group_id:
            group = get_object_or_404(Group, id=group_id)
            if not group.members.filter(id=self.request.user.id).exists():
                raise PermissionDenied("Not a group member")
            queryset = queryset.filter(group=group)
        
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('start_time')

    def perform_create(self, serializer):
        group = serializer.validated_data['group']
        if not group.members.filter(id=self.request.user.id).exists():
            raise PermissionDenied("Not a group member")
        
        session = serializer.save()
        SessionAttendance.objects.create(
            session=session,
            user=self.request.user,
            is_host=True
        )

    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        session = self.get_object()
        if session.attendees.filter(id=request.user.id).exists():
            return Response({'detail': 'Already attending'}, status=400)
        
        if session.max_attendees and session.attendees.count() >= session.max_attendees:
            return Response({'detail': 'Session is full'}, status=400)
        
        SessionAttendance.objects.create(
            session=session,
            user=request.user,
            is_host=False
        )
        return Response({'status': 'joined session'}, status=200)

    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        session = self.get_object()
        attendance = session.sessionattendance_set.filter(user=request.user).first()
        if not attendance:
            return Response({'detail': 'Not attending'}, status=400)
        
        if attendance.is_host and session.sessionattendance_set.filter(is_host=True).count() == 1:
            return Response({'detail': 'Cannot leave as the only host'}, status=400)
        
        attendance.delete()
        return Response({'status': 'left session'}, status=200)

    @action(detail=True, methods=['post'])
    def add_material(self, request, pk=None):
        session = self.get_object()
        resource_id = request.data.get('resource_id')
        
        try:
            resource = Resource.objects.get(id=resource_id)
            if resource.group != session.group:
                return Response({'detail': 'Resource not from this group'}, status=400)
            
            session.materials.add(resource)
            return Response({'status': 'material added'}, status=200)
        except Resource.DoesNotExist:
            return Response({'detail': 'Resource not found'}, status=404)

class GroupSessionView(generics.ListAPIView):
    serializer_class = SessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        group_id = self.kwargs['group_id']
        group = get_object_or_404(Group, id=group_id)
        if not group.members.filter(id=self.request.user.id).exists():
            raise PermissionDenied("Not a group member")
        return Session.objects.filter(group=group).order_by('start_time')
    

class NotificationSettingsViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return NotificationSettings.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)