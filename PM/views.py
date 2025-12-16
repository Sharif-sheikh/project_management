from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
import random
from django.views.decorators.http import require_POST

from .models import Project, Task, Profile, EmailOTP,ProjectMessage
from .forms import UserRegisterForm, ProjectForm, TaskForm, ProfileForm,ProjectMessageForm
from .utils import is_project_team_member

def generate_otp():
    return str(random.randint(100000, 999999))

def home(request):
    return render(request, "home.html")
# ---------------- AUTH VIEWS ----------------

def register(request):
    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            otp = generate_otp()
            EmailOTP.objects.create(user=user, otp=otp)
            send_mail("Your OTP Code", f"Your OTP is {otp}", "shorif.12005011@student.brur.ac.bd", [user.email])
            messages.info(request, "Check your email for OTP.")
            return redirect('email_verification')
    else:
        form = UserRegisterForm()
    return render(request, "register.html", {"form": form})

def email_verification(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        otp_input = request.POST.get('otp')
        try:
            user = User.objects.get(username=username)
            email_otp = EmailOTP.objects.get(user=user)
            if email_otp.otp == otp_input:
                user.is_active = True
                user.save()
                email_otp.is_verified = True
                email_otp.save()
                messages.success(request, "Email verified! You can login now.")
                return redirect('login')
            else:
                messages.error(request, "Invalid OTP.")
        except:
            messages.error(request, "Invalid user or OTP.")
    return render(request, 'email_verification.html')
def reset_password(request):
    if request.method == 'POST':
        otp = request.POST.get('otp')
        new_pass = request.POST.get('new_password')
        username = request.session.get('reset_user')
        user = User.objects.get(username=username)
        email_otp = EmailOTP.objects.get(user=user)
        if email_otp.otp == otp:
            user.set_password(new_pass)
            user.save()
            messages.success(request, "Password reset successful! Login again.")
            return redirect('login')
        else:
            messages.error(request, "Invalid OTP")
    return render(request, 'reset_password.html')

def user_login(request):
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("dashboard")
    else:
        form = AuthenticationForm()
    return render(request, "login.html", {"form": form})


@login_required
def user_logout(request):
    logout(request)
    return redirect("login")

# ---------------- FORGOT PASSWORD ----------------

def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            otp = generate_otp()
            EmailOTP.objects.update_or_create(user=user, defaults={'otp': otp})
            send_mail("Password Reset OTP", f"Your OTP is {otp}", "shorif.12005011@student.brur.ac.bd", [user.email])
            request.session['reset_user'] = user.username
            messages.info(request, "OTP sent to your email.")
            return redirect('reset_password')
        except User.DoesNotExist:
            messages.error(request, "Email not found.")
    return render(request, 'forgot_password.html')
# def forgot_password(request):
#     if request.method == "POST":
#         form = PasswordResetForm(request.POST)
#         if form.is_valid():
#             email = form.cleaned_data["email"]
#             users = User.objects.filter(email=email)
#             if users.exists():
#                 user = users.first()
#                 subject = "Password Reset Request"
#                 message = "Click the link to reset your password."
#                 send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])
#                 messages.success(request, "Password reset instructions sent to your email.")
#                 return redirect("login")
#             else:
#                 messages.error(request, "No account found with this email.")
#     else:
#         form = PasswordResetForm()
#     return render(request, "forgot_password.html", {"form": form})


# ---------------- DASHBOARD ----------------

@login_required
def dashboard(request):
    my_projects = Project.objects.filter(manager=request.user)
    assigned_tasks = Task.objects.filter(assignee=request.user)
    return render(request, "dashboard.html", {
        "my_projects": my_projects,
        "assigned_tasks": assigned_tasks
    })


# ---------------- PROJECT VIEWS ----------------

@login_required
def project_list(request):
    user = request.user
    projects = Project.objects.filter(Q(manager=user) | Q(client=user))
    return render(request, "project_list.html", {"projects": projects})


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    tasks = project.tasks.all()
    return render(request, "project_detail.html", {
        "project": project,
        "tasks": tasks,
        "progress": project.progress
    })


@login_required
def project_create(request):
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Project created successfully!")
            return redirect("project_list")
    else:
        form = ProjectForm()
    return render(request, "project_form.html", {"form": form})


@login_required
def project_edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "Project updated successfully!")
            return redirect("project_detail", pk=pk)
    else:
        form = ProjectForm(instance=project)
    return render(request, "project_form.html", {"form": form})


@login_required
def project_delete(request, pk):
    project = get_object_or_404(Project, pk=pk)
    project.delete()
    messages.success(request, "Project deleted.")
    return redirect("project_list")


# ---------------- TASK VIEWS ----------------

@login_required
def task_create(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.project = project
            task.save()
            messages.success(request, "Task created successfully!")
            return redirect("project_detail", pk=project.id)
    else:
        form = TaskForm()
    return render(request, "task_form.html", {"form": form, "project": project})


@login_required
def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk)
    project = task.project
    if project.manager != request.user:
        return HttpResponseForbidden("Only the project manager can edit this project.")
    task = get_object_or_404(Task, pk=pk)
    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, "Task updated successfully!")
            return redirect("project_detail", pk=task.project.id)
    else:
        form = TaskForm(instance=task)
    return render(request, "task_form.html", {"form": form, "project": task.project})


@login_required
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    project = task.project
    if project.manager != request.user:
        return HttpResponseForbidden("<h2>Only the project manager can delete this project.</h2>")
   
    project_id = task.project.id
    task.delete()
    messages.success(request, "Task deleted.")
    return redirect("project_detail", pk=project_id)


@login_required
def task_update_status(request, pk, status):
    task = get_object_or_404(Task, pk=pk, assignee=request.user)
    task.status = status
    task.save()
    messages.success(request, f"Task marked as {status}.")
    return redirect("dashboard")


# ---------------- PROFILE VIEWS ----------------

@login_required
def profile_view(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    return render(request, "profile.html", {"profile": profile})


@login_required
def profile_edit(request):
    profile = request.user.profile
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile)
    return render(request, "profile_edit.html", {"form": form})

# ---------------- PROJECT CHAT VIEWS ----------------





@login_required
def project_chat(request, pk):
    project = get_object_or_404(Project, pk=pk)

    if not is_project_team_member(request.user, project):
        return HttpResponseForbidden("You are not allowed to access this chat.")

    messages_list = project.messages.order_by("created_at")  # recommended

    if request.method == "POST":
        form = ProjectMessageForm(request.POST, request.FILES)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.project = project
            msg.user = request.user

            # ✅ Safety: make sure reply_to belongs to this project
            if msg.reply_to and msg.reply_to.project_id != project.id:
                msg.reply_to = None

            msg.save()
            return redirect("project_chat", pk=project.id)
    else:
        form = ProjectMessageForm()

    return render(request, "project_chat.html", {
        "project": project,
        "messages": messages_list,
        "form": form
    })




@require_POST
@login_required
def project_message_delete(request, pk, message_id):
    project = get_object_or_404(Project, pk=pk)

    # Permission check (same as chat)
    if not is_project_team_member(request.user, project):
        return HttpResponseForbidden("You are not allowed to access this chat.")

    msg = get_object_or_404(ProjectMessage, id=message_id, project=project)

    # Allow delete: message owner OR project manager
    if msg.user != request.user and project.manager != request.user:
        return HttpResponseForbidden("You cannot delete this message.")

    msg.delete()
    return redirect("project_chat", pk=project.id)