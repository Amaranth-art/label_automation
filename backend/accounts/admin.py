from django.contrib import admin

from .models import Department, UserProfile


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
	list_display = ('code', 'name', 'name_zh')
	search_fields = ('code', 'name', 'name_zh')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
	list_display = ('display_name', 'user', 'department', 'role', 'supervisor')
	list_filter = ('department', 'role')
	search_fields = ('display_name', 'user__username', 'user__email')
