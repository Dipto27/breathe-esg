"""
Management command to set up a demo client with a user.
Run: python manage.py setup_demo
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from emissions.models import Client, UserClientMembership


class Command(BaseCommand):
    help = 'Create demo client and analyst user'

    def handle(self, *args, **options):
        # Create demo client
        client, created = Client.objects.get_or_create(
            slug='acme-corp',
            defaults={'name': 'ACME Corporation'}
        )
        if created:
            self.stdout.write(f'Created client: {client.name}')

        # Create analyst user
        user, created = User.objects.get_or_create(
            username='analyst',
            defaults={
                'email': 'analyst@acme.com',
                'first_name': 'Alex',
                'last_name': 'Chen',
            }
        )
        if created:
            user.set_password('demo1234')
            user.save()
            self.stdout.write(f'Created user: analyst / demo1234')

        # Create admin user
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@breatheesg.com',
                'first_name': 'Admin',
                'last_name': 'User',
                'is_superuser': True,
                'is_staff': True,
            }
        )
        if created:
            admin.set_password('admin1234')
            admin.save()
            self.stdout.write(f'Created superuser: admin / admin1234')

        # Link user to client
        membership, _ = UserClientMembership.objects.get_or_create(
            user=user, client=client, defaults={'role': 'ANALYST'}
        )
        UserClientMembership.objects.get_or_create(
            user=admin, client=client, defaults={'role': 'ADMIN'}
        )

        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Demo setup complete!\n'
            f'  Client: {client.name} (id={client.id})\n'
            f'  Analyst login: analyst / demo1234\n'
            f'  Admin login: admin / admin1234\n'
        ))
