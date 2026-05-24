from django.contrib.auth import authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from emissions.models import UserClientMembership


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username', '')
        password = request.data.get('password', '')
        user = authenticate(username=username, password=password)
        if not user:
            return Response({'error': 'Invalid credentials'}, status=401)
        
        refresh = RefreshToken.for_user(user)
        memberships = UserClientMembership.objects.filter(user=user).select_related('client')
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.get_full_name(),
                'is_superuser': user.is_superuser,
            },
            'clients': [
                {'id': m.client.id, 'name': m.client.name, 'slug': m.client.slug, 'role': m.role}
                for m in memberships
            ]
        })


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        memberships = UserClientMembership.objects.filter(user=user).select_related('client')
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'full_name': user.get_full_name(),
            'is_superuser': user.is_superuser,
            'clients': [
                {'id': m.client.id, 'name': m.client.name, 'slug': m.client.slug, 'role': m.role}
                for m in memberships
            ]
        })
