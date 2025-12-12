from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Project, Task, Profile, ProjectMessage


class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]
        widgets = {
            "password1": forms.PasswordInput(attrs={"class": "form-control"}),
            "password2": forms.PasswordInput(attrs={"class": "form-control"}),
        }


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "description", "start_date", "end_date", "manager", "client"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control"}),
            "manager": forms.Select(attrs={"class": "form-select"}),
            "client": forms.Select(attrs={"class": "form-select", }),
            "start_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class TaskForm(forms.ModelForm):
    deadline = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )

    class Meta:
        model = Task
        fields = ["title", "description", "assignee", "deadline", "status"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control"}),
            "assignee": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["avatar", "github", "linkedin", "address", "occupation"]



class ProjectMessageForm(forms.ModelForm):
    class Meta:
        model = ProjectMessage
        fields = ["text", "file"]

        widgets = {
            "text": forms.Textarea(attrs={
                "rows": 2,
                "class": "form-control",
                "placeholder": "Write a message..."
            }),
            "file": forms.ClearableFileInput(attrs={"class": "form-control"})
        }
