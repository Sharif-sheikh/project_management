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

from .models import Project, Task, Profile, EmailOTP, ProjectMessage, TaskInvite
from .forms import UserRegisterForm, ProjectForm, TaskForm, ProfileForm, ProjectMessageForm
from .utils import is_project_team_member

def generate_otp():
    return str(random.randint(100000, 999999))


def create_task_invitation(email, inviter, project, request):
    """Create a task invitation and send email"""
    # Check rate limiting: max 10 invites per user per day
    today = timezone.now().date()
    today_start = timezone.datetime.combine(today, timezone.datetime.min.time())
    today_start = timezone.make_aware(today_start)
    
    invites_today = TaskInvite.objects.filter(
        inviter=inviter,
        created_at__gte=today_start
    ).count()
    
    if invites_today >= 10:
        return False, "You have reached the maximum number of invitations for today (10)."
    
    # Create invitation
    invite = TaskInvite.objects.create(
        email=email,
        inviter=inviter,
        project=project
    )
    
    # Build invitation URL
    invite_url = request.build_absolute_uri(
        f'/invite/{invite.token}/'
    )
    
    # Send email
    subject = f"You've been invited to join a project on ProjectFlow"
    message = f"""Hello,

{inviter.username} has invited you to collaborate on a project: {project.name}.

To accept this invitation and view your assigned tasks, please click the link below:

{invite_url}

If you already have an account, you'll be logged in. Otherwise, you can create a new account.

Best regards,
ProjectFlow Team
"""
    
    try:
        send_mail(subject, message, settings.EMAIL_HOST_USER, [email])
        return True, "Invitation sent successfully."
    except Exception as e:
        # Keep the invite even if email fails (e.g., in testing/dev environments)
        # In production, you may want to handle this differently
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send invitation email to {email}: {str(e)}")
        return True, "Invitation created but email could not be sent."


def handle_email_assignment(task, assignee_email, inviter, project, request):
    """Handle task assignment by email - checks if user exists or creates invitation"""
    try:
        existing_user = User.objects.get(email=assignee_email)
        task.assignee = existing_user
        task.assignee_email = None
        task.save()
        return True, "Task assigned to existing user."
    except User.DoesNotExist:
        # Create invitation
        task.assignee = None
        task.assignee_email = assignee_email
        task.save()
        
        success, msg = create_task_invitation(assignee_email, inviter, project, request)
        if success:
            return True, "Task created and invitation sent!"
        else:
            return False, f"Task created but invitation failed: {msg}"


def home(request):
    return render(request, "home.html")
# ---------------- AUTH VIEWS ----------------

def register(request):
    invited_email = request.session.get('invited_email')
    
    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            # If there's an invited email, validate it matches
            if invited_email and form.cleaned_data['email'] != invited_email:
                messages.error(request, "Email must match the invitation email.")
                return render(request, "register.html", {"form": form, "invited_email": invited_email})
            
            user = form.save()
            otp = generate_otp()
            EmailOTP.objects.create(user=user, otp=otp)
            send_mail("Your OTP Code", f"Your OTP is {otp}", settings.EMAIL_HOST_USER, [user.email])
            
            # Link any pending tasks to this user
            if invited_email:
                tasks_updated = Task.objects.filter(assignee_email=invited_email).update(
                    assignee=user,
                    assignee_email=None
                )
                # Mark invitations as accepted
                TaskInvite.objects.filter(email=invited_email, is_active=True).update(
                    accepted_at=timezone.now(),
                    is_active=False
                )
                # Clear session
                del request.session['invited_email']
                if tasks_updated > 0:
                    messages.success(request, f"Welcome! {tasks_updated} task(s) have been assigned to you.")
            
            messages.info(request, "Check your email for OTP.")
            return redirect('email_verification')
    else:
        # Pre-fill email if invited
        initial_data = {}
        if invited_email:
            initial_data['email'] = invited_email
        form = UserRegisterForm(initial=initial_data)
    
    return render(request, "register.html", {"form": form, "invited_email": invited_email})

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
    
    # Check for pending tasks assigned by email
    pending_email_tasks = Task.objects.filter(
        assignee_email=request.user.email,
        assignee__isnull=True
    )
    if pending_email_tasks.exists():
        # Auto-link them
        pending_email_tasks.update(assignee=request.user, assignee_email=None)
        assigned_tasks = Task.objects.filter(assignee=request.user)
        messages.info(request, f"{pending_email_tasks.count()} pending task(s) have been assigned to you.")
    
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
            
            # Handle email assignment
            assignee_email = form.cleaned_data.get('assignee_email')
            if assignee_email:
                success, msg = handle_email_assignment(task, assignee_email, request.user, project, request)
                if success:
                    messages.success(request, msg)
                else:
                    messages.warning(request, msg)
                return redirect("project_detail", pk=project.id)
            
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
    
    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            task = form.save(commit=False)
            
            # Handle email assignment
            assignee_email = form.cleaned_data.get('assignee_email')
            if assignee_email:
                success, msg = handle_email_assignment(task, assignee_email, request.user, project, request)
                if success:
                    messages.success(request, msg)
                else:
                    messages.warning(request, msg)
                return redirect("project_detail", pk=task.project.id)
            
            task.save()
            messages.success(request, "Task updated successfully!")
            return redirect("project_detail", pk=task.project.id)
    else:
        # Pre-fill assignee_email if task has a pending email
        initial_data = {}
        if task.assignee_email:
            initial_data['assignee_email'] = task.assignee_email
        form = TaskForm(instance=task, initial=initial_data)
    
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


# ---------------- INVITE VIEWS ----------------

def accept_invite(request, token):
    """Handle invitation acceptance"""
    invite = get_object_or_404(TaskInvite, token=token, is_active=True)
    
    # Check if user exists with this email
    try:
        existing_user = User.objects.get(email=invite.email)
        # User exists - log them in or redirect to login
        if request.user.is_authenticated:
            if request.user.email == invite.email:
                # Already logged in with correct account
                # Link pending tasks
                Task.objects.filter(assignee_email=invite.email).update(
                    assignee=request.user,
                    assignee_email=None
                )
                invite.accepted_at = timezone.now()
                invite.is_active = False
                invite.save()
                messages.success(request, "Invitation accepted! Tasks have been assigned to you.")
                return redirect("dashboard")
            else:
                messages.warning(request, "Please log in with the invited email address.")
                return redirect("login")
        else:
            # Not logged in - redirect to login
            messages.info(request, f"Please log in with {invite.email} to accept this invitation.")
            return redirect("login")
    except User.DoesNotExist:
        # User doesn't exist - redirect to registration with email in session
        request.session['invited_email'] = invite.email
        messages.info(request, "Please create an account to accept this invitation.")
        return redirect("register")


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