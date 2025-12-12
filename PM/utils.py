from .models import Task

def is_project_team_member(user, project):
    if user == project.manager:
        return True
    if hasattr(project, "client") and user == project.client:
        return True
    return Task.objects.filter(project=project, assignee=user).exists()
