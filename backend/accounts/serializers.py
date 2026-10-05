from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from .models import Department, UserProfile

User = get_user_model()


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ("id", "name", "name_zh", "code")


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ("id", "name")


class UserSummarySerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source="profile.display_name", read_only=True)
    role = serializers.CharField(source="profile.role", read_only=True)
    department = DepartmentSerializer(source="profile.department", read_only=True)
    supervisor_id = serializers.IntegerField(source="profile.supervisor_id", read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "display_name", "role", "department", "supervisor_id")


class CurrentUserSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    supervisor = serializers.SerializerMethodField()
    is_staff = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "display_name", "role", "department", "supervisor", "is_staff")

    def get_profile(self, user):
        try:
            return user.profile
        except UserProfile.DoesNotExist:
            return None

    def get_display_name(self, user):
        profile = self.get_profile(user)
        return profile.display_name if profile else user.get_full_name() or user.username

    def get_role(self, user):
        profile = self.get_profile(user)
        return profile.role if profile else None

    def get_department(self, user):
        profile = self.get_profile(user)
        return DepartmentSerializer(profile.department).data if profile else None

    def get_supervisor(self, user):
        profile = self.get_profile(user)
        return UserSummarySerializer(profile.supervisor).data if profile and profile.supervisor_id else None


class UserAdminSerializer(serializers.ModelSerializer):
    department_id = serializers.PrimaryKeyRelatedField(
        source="department", queryset=Department.objects.all(), write_only=True
    )
    role = serializers.ChoiceField(choices=UserProfile.Role.choices, write_only=True)
    supervisor_id = serializers.PrimaryKeyRelatedField(
        source="supervisor", queryset=User.objects.all(), allow_null=True, required=False, write_only=True
    )
    display_name = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    groups = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), many=True, required=False)
    profile = UserSummarySerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            "id", "username", "password", "first_name", "last_name", "email", "is_active", "groups",
            "department_id", "role", "supervisor_id", "display_name", "profile",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        profile = self.instance.profile if self.instance else None
        department = attrs.get("department", profile.department if profile else None)
        role = attrs.get("role", profile.role if profile else None)
        supervisor = attrs.get("supervisor", profile.supervisor if profile else None)
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": _("A password is required for a new user.")})
        if role == UserProfile.Role.STAFF and supervisor is None:
            raise serializers.ValidationError({"supervisor_id": _("Staff members must have a supervisor.")})
        if role == UserProfile.Role.SUPERVISOR and supervisor is not None:
            raise serializers.ValidationError({"supervisor_id": _("A supervisor cannot report to another supervisor.")})
        if supervisor is not None:
            if not hasattr(supervisor, "profile"):
                raise serializers.ValidationError({"supervisor_id": _("The selected user has no profile.")})
            if supervisor.profile.department_id != department.id:
                raise serializers.ValidationError({"supervisor_id": _("Supervisor must belong to the same department.")})
            if supervisor.profile.role != UserProfile.Role.SUPERVISOR:
                raise serializers.ValidationError({"supervisor_id": _("The selected user is not a supervisor.")})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        department = validated_data.pop("department")
        role = validated_data.pop("role")
        supervisor = validated_data.pop("supervisor", None)
        display_name = validated_data.pop("display_name")
        groups = validated_data.pop("groups", [])
        user = User.objects.create_user(password=password, **validated_data)
        user.groups.set(groups)
        UserProfile.objects.create(
            user=user,
            department=department,
            role=role,
            supervisor=supervisor,
            display_name=display_name,
        )
        return user

    @transaction.atomic
    def update(self, instance, validated_data):
        profile = instance.profile
        password = validated_data.pop("password", None)
        department = validated_data.pop("department", profile.department)
        role = validated_data.pop("role", profile.role)
        supervisor = validated_data.pop("supervisor", profile.supervisor)
        display_name = validated_data.pop("display_name", profile.display_name)
        groups = validated_data.pop("groups", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        if groups is not None:
            instance.groups.set(groups)
        profile.department = department
        profile.role = role
        profile.supervisor = supervisor
        profile.display_name = display_name
        profile.full_clean()
        profile.save()
        return instance