from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    avatar = models.URLField(blank=True, default='')
    bio = models.TextField(blank=True)
    
    class Meta:
        db_table = 'api_user'
    
    @property
    def name(self):
        return f"{self.first_name} {self.last_name}" if self.first_name else self.username
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    study_hours = models.PositiveIntegerField(default=0)
    sessions_attended = models.PositiveIntegerField(default=0)
    resources_shared = models.PositiveIntegerField(default=0)
    groups_joined = models.PositiveIntegerField(default=0)
    
class NotificationSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notifications')
    email_notifications = models.BooleanField(default=True)
    session_reminders = models.BooleanField(default=True)
    group_messages = models.BooleanField(default=True)
    resource_updates = models.BooleanField(default=True)
    new_members = models.BooleanField(default=True)

class Group(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    subject = models.CharField(max_length=100)
    members = models.ManyToManyField(User, through='GroupMembership')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_groups')
    created_at = models.DateTimeField(auto_now_add=True)
    avatar = models.URLField(blank=True, null=True)
    last_activity = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class GroupMembership(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('member', 'Member'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'group')

class ChatMessage(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    attachments = models.ManyToManyField('Resource', blank=True)
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.group.last_activity = timezone.now()
        self.group.save()

    class Meta:
        ordering = ['-timestamp']

class Resource(models.Model):
    FILE_TYPES = (
        ('pdf', 'PDF'),
        ('docx', 'DOCX'),
        ('pptx', 'PPTX'),
        ('png', 'PNG'),
        ('jpg', 'JPG'),
        ('js', 'JavaScript'),
        ('txt', 'Text'),
    )
    
    title = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10, choices=FILE_TYPES)
    file = models.FileField(upload_to='resources/')
    description = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    download_count = models.PositiveIntegerField(default=0)
    is_favorite = models.BooleanField(default=False)
    tags = models.JSONField(default=list)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.group.last_activity = timezone.now()
        self.group.save()

    def __str__(self):
        return self.title

class Session(models.Model):
    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=255)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    description = models.TextField(blank=True)
    agenda = models.JSONField(default=list)
    location = models.CharField(max_length=255, blank=True)
    max_attendees = models.PositiveIntegerField(blank=True, null=True)
    is_virtual = models.BooleanField(default=False)
    meeting_link = models.URLField(blank=True)
    materials = models.ManyToManyField(Resource, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='upcoming')
    notes = models.TextField(blank=True)
    attendees = models.ManyToManyField(
        User, 
        through='SessionAttendance',
        related_name='attended_sessions'
    )
    def save(self, *args, **kwargs):
        now = timezone.now()
        if self.start_time <= now <= self.end_time:
            self.status = 'ongoing'
        elif now > self.end_time:
            self.status = 'completed'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} (Group: {self.group.name})"

class SessionAttendance(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_host = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('session', 'user')