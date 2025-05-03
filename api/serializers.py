from rest_framework import serializers
from .models import *
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.utils import timezone

User = get_user_model()
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['study_hours', 'sessions_attended', 'resources_shared', 'groups_joined']

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'avatar', 'bio', 'name')
        extra_kwargs = {'password': {'write_only': True}}

    def get_name(self, obj):
        return obj.name
    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password']
        )
        user.avatar = validated_data.get('avatar', '')
        user.bio = validated_data.get('bio', '')
        user.save()
        return user
    

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data.update({
            'user': UserSerializer(self.user).data
        })
        return data

class GroupMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()

    class Meta:
        model = GroupMembership
        fields = ['id', 'user', 'name', 'email', 'role', 'joined_at']
    
    def get_name(self, obj):
        return obj.user.name
    
    def get_email(self, obj):
        return obj.user.email

class GroupSerializer(serializers.ModelSerializer):
    members = GroupMemberSerializer(source='groupmembership_set', many=True, read_only=True)
    created_by = UserSerializer(read_only=True)
    member_count = serializers.SerializerMethodField()
    is_new = serializers.SerializerMethodField()
    last_activity = serializers.SerializerMethodField()
    recent_activity = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ['id', 'name', 'description', 'subject', 'avatar', 
                 'members', 'created_by', 'created_at', 'member_count',
                 'is_new', 'last_activity','recent_activity']
    
    def get_member_count(self, obj):
        return obj.members.count()
    
    def get_is_new(self, obj):
        return (timezone.now() - obj.created_at).days < 7
    
    def get_last_activity(self, obj):
        last_message = obj.messages.order_by('-timestamp').first()
        if last_message:
            return self.format_timesince(last_message.timestamp)
        return "No activity yet"
    
    def format_timesince(self, dt):
        diff = timezone.now() - dt
        if diff.days > 0:
            return f"{diff.days} days ago"
        seconds = diff.seconds
        if seconds < 60:
            return "Just now"
        if seconds < 3600:
            return f"{seconds//60} minutes ago"
        return f"{seconds//3600} hours ago"
    def get_recent_activity(self, obj):
        return {
            'type': 'message',  # or 'resource', 'session'
            'content': obj.messages.last().message if obj.messages.exists() else None,
            'timestamp': obj.last_activity
        }
    

class ResourceSerializer(serializers.ModelSerializer):
    uploaded_by = UserSerializer(read_only=True)
    uploaded_at = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = ['id', 'title', 'file_type', 'file', 'description', 
                 'uploaded_by', 'uploaded_at', 'file_size', 'download_url',
                 'preview_url', 'group', 'download_count', 'is_favorite', 'tags']
        read_only_fields = ['uploaded_by', 'uploaded_at', 'download_count']
    
    def get_uploaded_at(self, obj):
        return self.format_timesince(obj.uploaded_at)
    
    def get_file_size(self, obj):
        try:
            size = obj.file.size
            if size < 1024:
                return f"{size} B"
            if size < 1024*1024:
                return f"{size/1024:.1f} KB"
            return f"{size/(1024*1024):.1f} MB"
        except:
            return "0 B"
    
    def get_download_url(self, obj):
        return f"/api/resources/{obj.id}/download/"
    
    def get_preview_url(self, obj):
        if obj.file_type in ['pdf', 'png', 'jpg']:
            return f"/api/resources/{obj.id}/preview/"
        return None
    
    def format_timesince(self, dt):
        diff = timezone.now() - dt
        if diff.days > 7:
            return "Last week"
        if diff.days > 0:
            return f"{diff.days} days ago"
        seconds = diff.seconds
        if seconds < 60:
            return "Just now"
        if seconds < 3600:
            return f"{seconds//60} minutes ago"
        return f"{seconds//3600} hours ago"

class ChatMessageSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_avatar = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatMessage
        fields = ['id', 'group', 'user', 'user_name', 'user_avatar', 
                 'message', 'timestamp', 'attachments']
        read_only_fields = ['user', 'timestamp']

    def get_user_name(self, obj):
        return obj.user.name
    
    def get_user_avatar(self, obj):
        return obj.user.avatar

class SessionAttendeeSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    is_host = serializers.BooleanField()

    class Meta:
        model = SessionAttendance
        fields = ['id', 'user', 'name', 'avatar', 'is_host']
    
    def get_name(self, obj):
        return obj.user.name
    
    def get_avatar(self, obj):
        return obj.user.avatar

class SessionMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = ['id', 'title', 'file_type']

class SessionSerializer(serializers.ModelSerializer):
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all())
    group_name = serializers.SerializerMethodField()
    attendees = SessionAttendeeSerializer(source='sessionattendance_set', many=True, read_only=True)
    materials = SessionMaterialSerializer(many=True, read_only=True)
    start = serializers.DateTimeField(source='start_time')
    end = serializers.DateTimeField(source='end_time')

    class Meta:
        model = Session
        fields = ['id', 'title', 'start', 'end', 'group', 'group_name', 
                 'description', 'agenda', 'location', 'attendees', 
                 'max_attendees', 'is_virtual', 'meeting_link', 
                 'materials', 'status', 'notes']
    
    def get_group_name(self, obj):
        return obj.group.name
    
    def validate(self, data):
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("End time must be after start time")
        return data
    
class NotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSettings
        fields = '__all__'
        read_only_fields = ('user',)