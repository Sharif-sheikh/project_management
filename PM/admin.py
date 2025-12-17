from django.contrib import admin
from .models import Project, Task, Profile, EmailOTP, TaskInvite

# Register your models here.
admin.site.register(Project)
admin.site.register(Task)
admin.site.register(Profile)
admin.site.register(EmailOTP)
admin.site.register(TaskInvite)
    