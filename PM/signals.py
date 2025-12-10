from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile, Task
from django.core.mail import send_mail
from django.conf import settings


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=Task)
def notify_assignee(sender, instance, created, **kwargs):
    if created and instance.assignee:
        subject = f"New Task Assigned: {instance.title}"
        message = f"Hello {instance.assignee.username},\n\nYou have been assigned a new task: {instance.title}.\nDeadline: {instance.deadline}.\n\nPlease log in to update progress."
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [instance.assignee.email])
