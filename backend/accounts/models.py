from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class Department(models.Model):
	name = models.CharField(max_length=100, unique=True)
	name_zh = models.CharField(max_length=100)
	code = models.SlugField(max_length=30, unique=True)

	class Meta:
		ordering = ("code",)
		verbose_name = "Department"
		verbose_name_plural = "Departments"

	def __str__(self):
		return self.name


class UserProfile(models.Model):
	class Role(models.TextChoices):
		SUPERVISOR = "supervisor", "Supervisor"
		STAFF = "staff", "Staff"

	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="profile",
	)
	department = models.ForeignKey(
		Department,
		on_delete=models.PROTECT,
		related_name="profiles",
	)
	display_name = models.CharField(max_length=150)
	role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF)
	supervisor = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="direct_reports",
	)

	class Meta:
		ordering = ("department__code", "display_name")

	def clean(self):
		if self.role == self.Role.SUPERVISOR and self.supervisor_id:
			raise ValidationError({"supervisor": _("A supervisor cannot report to another supervisor.")})
		if self.role == self.Role.STAFF and not self.supervisor_id:
			raise ValidationError({"supervisor": _("Staff members must have a supervisor.")})
		if self.supervisor_id:
			try:
				supervisor_profile = self.supervisor.profile
			except UserProfile.DoesNotExist:
				raise ValidationError({"supervisor": _("The selected supervisor has no profile.")}) from None
			if supervisor_profile.department_id != self.department_id:
				raise ValidationError({"supervisor": _("Supervisor must belong to the same department.")})
			if supervisor_profile.role != self.Role.SUPERVISOR:
				raise ValidationError({"supervisor": _("The selected user is not a supervisor.")})

	def __str__(self):
		return self.display_name
