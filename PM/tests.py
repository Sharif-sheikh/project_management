from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from .models import Project, Task, TaskInvite


class TaskInviteTestCase(TestCase):
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create test users
        self.manager = User.objects.create_user(
            username='manager',
            email='manager@test.com',
            password='testpass123'
        )
        self.manager.is_active = True
        self.manager.save()
        
        # Create a test project
        self.project = Project.objects.create(
            name='Test Project',
            description='Test Description',
            manager=self.manager,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30)
        )
    
    def test_task_invite_creation(self):
        """Test that TaskInvite is created with valid token"""
        invite = TaskInvite.objects.create(
            email='newuser@test.com',
            inviter=self.manager,
            project=self.project
        )
        
        self.assertIsNotNone(invite.token)
        self.assertTrue(len(invite.token) > 0)
        self.assertTrue(invite.is_active)
        self.assertIsNone(invite.accepted_at)
        self.assertEqual(invite.email, 'newuser@test.com')
    
    def test_task_creation_with_email(self):
        """Test creating a task with an email assignment"""
        self.client.login(username='manager', password='testpass123')
        
        # Create a task with email assignment
        response = self.client.post(
            reverse('task_create', kwargs={'project_id': self.project.id}),
            {
                'title': 'Test Task',
                'description': 'Test Description',
                'assignee_email': 'invited@test.com',
                'deadline': (timezone.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M'),
                'status': 'todo'
            }
        )
        
        # Check task was created with email
        task = Task.objects.filter(title='Test Task').first()
        self.assertIsNotNone(task)
        self.assertEqual(task.assignee_email, 'invited@test.com')
        self.assertIsNone(task.assignee)
        
        # Check invitation was created
        invite = TaskInvite.objects.filter(email='invited@test.com').first()
        self.assertIsNotNone(invite)
        self.assertTrue(invite.is_active)
    
    def test_task_creation_with_existing_user_email(self):
        """Test creating a task with an email of an existing user"""
        # Create another user
        existing_user = User.objects.create_user(
            username='existing',
            email='existing@test.com',
            password='testpass123'
        )
        existing_user.is_active = True
        existing_user.save()
        
        self.client.login(username='manager', password='testpass123')
        
        # Create task with existing user's email
        response = self.client.post(
            reverse('task_create', kwargs={'project_id': self.project.id}),
            {
                'title': 'Test Task 2',
                'description': 'Test Description',
                'assignee_email': 'existing@test.com',
                'deadline': (timezone.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M'),
                'status': 'todo'
            }
        )
        
        # Check task was assigned to existing user
        task = Task.objects.filter(title='Test Task 2').first()
        self.assertIsNotNone(task)
        self.assertEqual(task.assignee, existing_user)
        self.assertIsNone(task.assignee_email)
    
    def test_registration_links_pending_tasks(self):
        """Test that registering with invited email links pending tasks"""
        # Create a task with email assignment
        task = Task.objects.create(
            project=self.project,
            title='Pending Task',
            description='Test',
            assignee_email='newuser@test.com',
            deadline=timezone.now() + timedelta(days=7),
            status='todo'
        )
        
        # Create invitation
        invite = TaskInvite.objects.create(
            email='newuser@test.com',
            inviter=self.manager,
            project=self.project
        )
        
        # Simulate invitation acceptance by setting session
        session = self.client.session
        session['invited_email'] = 'newuser@test.com'
        session.save()
        
        # Register new user
        response = self.client.post(
            reverse('register'),
            {
                'username': 'newuser',
                'email': 'newuser@test.com',
                'password1': 'ComplexPass123!',
                'password2': 'ComplexPass123!'
            }
        )
        
        # Check that task is now assigned to the new user
        new_user = User.objects.filter(username='newuser').first()
        if new_user:
            task.refresh_from_db()
            self.assertEqual(task.assignee, new_user)
            self.assertIsNone(task.assignee_email)
            
            # Check invitation is marked as accepted
            invite.refresh_from_db()
            self.assertFalse(invite.is_active)
            self.assertIsNotNone(invite.accepted_at)
    
    def test_invite_acceptance_existing_user(self):
        """Test invite acceptance when user already exists"""
        # Create existing user
        existing_user = User.objects.create_user(
            username='existing',
            email='existing@test.com',
            password='testpass123'
        )
        existing_user.is_active = True
        existing_user.save()
        
        # Create task with email assignment
        task = Task.objects.create(
            project=self.project,
            title='Task for Existing',
            description='Test',
            assignee_email='existing@test.com',
            deadline=timezone.now() + timedelta(days=7),
            status='todo'
        )
        
        # Create invitation
        invite = TaskInvite.objects.create(
            email='existing@test.com',
            inviter=self.manager,
            project=self.project
        )
        
        # Login as existing user
        self.client.login(username='existing', password='testpass123')
        
        # Accept invitation
        response = self.client.get(
            reverse('accept_invite', kwargs={'token': invite.token})
        )
        
        # Check task is assigned
        task.refresh_from_db()
        self.assertEqual(task.assignee, existing_user)
        self.assertIsNone(task.assignee_email)
        
        # Check invitation is marked as accepted
        invite.refresh_from_db()
        self.assertFalse(invite.is_active)
        self.assertIsNotNone(invite.accepted_at)
    
    def test_rate_limiting(self):
        """Test that invite rate limiting works"""
        self.client.login(username='manager', password='testpass123')
        
        # Create 10 invitations (the limit)
        for i in range(10):
            TaskInvite.objects.create(
                email=f'user{i}@test.com',
                inviter=self.manager,
                project=self.project
            )
        
        # Try to create 11th invitation via task creation
        response = self.client.post(
            reverse('task_create', kwargs={'project_id': self.project.id}),
            {
                'title': 'Test Task Limit',
                'description': 'Test',
                'assignee_email': 'user11@test.com',
                'deadline': (timezone.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M'),
                'status': 'todo'
            }
        )
        
        # Task should be created but with a warning message
        task = Task.objects.filter(title='Test Task Limit').first()
        self.assertIsNotNone(task)
    
    def test_form_validation_both_assignee_and_email(self):
        """Test that form validation prevents both assignee and email"""
        self.client.login(username='manager', password='testpass123')
        
        # Create another user for assignee
        assignee_user = User.objects.create_user(
            username='assignee',
            email='assignee@test.com',
            password='testpass123'
        )
        
        # Try to submit with both assignee and email
        response = self.client.post(
            reverse('task_create', kwargs={'project_id': self.project.id}),
            {
                'title': 'Invalid Task',
                'description': 'Test',
                'assignee': assignee_user.id,
                'assignee_email': 'another@test.com',
                'deadline': (timezone.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M'),
                'status': 'todo'
            }
        )
        
        # Should return form with errors
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please select either an existing assignee OR provide an email')
    
    def test_form_validation_neither_assignee_nor_email(self):
        """Test that form validation requires either assignee or email"""
        self.client.login(username='manager', password='testpass123')
        
        # Try to submit without assignee or email
        response = self.client.post(
            reverse('task_create', kwargs={'project_id': self.project.id}),
            {
                'title': 'Invalid Task 2',
                'description': 'Test',
                'deadline': (timezone.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M'),
                'status': 'todo'
            }
        )
        
        # Should return form with errors
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please either select an assignee or provide an email')
