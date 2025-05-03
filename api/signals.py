from django.db.models.signals import post_save
from django.dispatch import receiver
from api.models import GroupMembership, Resource  # Replace 'your_app' with the actual app name

@receiver(post_save, sender=Resource)
def update_resource_stats(sender, instance, created, **kwargs):
    if created:
        profile = instance.uploaded_by.profile
        profile.resources_shared += 1
        profile.save()

@receiver(post_save, sender=GroupMembership)
def update_group_stats(sender, instance, created, **kwargs):
    if created:
        profile = instance.user.profile
        profile.groups_joined += 1
        profile.save()