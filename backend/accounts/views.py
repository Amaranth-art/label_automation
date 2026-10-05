from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Department, UserProfile
from .serializers import (
    CurrentUserSerializer,
    DepartmentSerializer,
    GroupSerializer,
    UserAdminSerializer,
    UserSummarySerializer,
)

User = get_user_model()


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [permissions.IsAuthenticated()]
        return [permissions.IsAdminUser()]


class GroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Group.objects.all().order_by('name')
    serializer_class = GroupSerializer
    permission_classes = (permissions.IsAdminUser,)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related('profile__department', 'profile__supervisor')

    def get_queryset(self):
        queryset = super().get_queryset().filter(is_active=True, profile__isnull=False)
        user = self.request.user
        requested_department = self.request.query_params.get('department')
        if not user.is_staff and not requested_department:
            try:
                queryset = queryset.filter(profile__department=user.profile.department)
            except UserProfile.DoesNotExist:
                return queryset.none()
        department = self.request.query_params.get('department')
        role = self.request.query_params.get('role')
        supervisor = self.request.query_params.get('supervisor')
        if department:
            queryset = queryset.filter(profile__department_id=department)
        if role:
            queryset = queryset.filter(profile__role=role)
        if supervisor:
            queryset = queryset.filter(profile__supervisor_id=supervisor)
        return queryset

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return UserAdminSerializer
        if self.action == 'me':
            return CurrentUserSerializer
        return UserSummarySerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'me'):
            return [permissions.IsAuthenticated()]
        return [permissions.IsAdminUser()]

    @action(detail=False, methods=('get',), url_path='me')
    def me(self, request):
        return Response(self.get_serializer(request.user).data)


class CurrentUserView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        old_password = request.data.get('old_password', '')
        new_password = request.data.get('new_password', '')
        confirm_password = request.data.get('confirm_password', '')

        if not all(
            isinstance(value, str) and value
            for value in (old_password, new_password, confirm_password)
        ):
            return Response(
                {'code': 'required', 'detail': _('Please fill in all fields')},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not request.user.check_password(old_password):
            return Response(
                {'code': 'old_password_wrong', 'detail': _('Old password is incorrect')},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_password != confirm_password:
            return Response(
                {'code': 'not_match', 'detail': _('The two passwords do not match')},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_password == old_password:
            return Response(
                {'code': 'same_as_old', 'detail': _('New password cannot be the same as old password')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.set_password(new_password)
        request.user.save(update_fields=('password',))
        return Response({'detail': _('Password changed successfully')})
