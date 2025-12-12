from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Project Model
class Project(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    manager = models.ForeignKey(User, on_delete=models.CASCADE, related_name="managed_projects")
    client = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="client_projects")

    def __str__(self):
        return self.name

    @property
    def progress(self):
        total = self.tasks.count()
        if total == 0:
            return 0
        completed = self.tasks.filter(status="done").count()
        return int((completed / total) * 100)


# Task Model
class Task(models.Model):
    STATUS_CHOICES = [
        ("todo", "To Do"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    deadline = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="todo")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


# Profile Model (extra info for User)
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    avatar = models.ImageField(upload_to="avatars/", default="avatars/default.png", blank=True)
    github = models.URLField(blank=True, null=True)
    linkedin = models.URLField(blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    occupation = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

class EmailOTP(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    

class ProjectMessage(models.Model):
    project = models.ForeignKey("Project", on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField(blank=True)
    file = models.FileField(upload_to="chat_resources/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.project.name}"
