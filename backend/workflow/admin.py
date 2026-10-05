from django.contrib import admin

from .models import ApprovalFlow, ApprovalNode, LabelApplication, PackingList


@admin.register(PackingList)
class PackingListAdmin(admin.ModelAdmin):
	list_display = ('order_no', 'machine_type', 'uploader', 'status', 'created_at')
	list_filter = ('status', 'created_at')
	search_fields = ('order_no', 'machine_type', 'uploader__username')


@admin.register(LabelApplication)
class LabelApplicationAdmin(admin.ModelAdmin):
	list_display = ('packing_list', 'applicant', 'is_new_model', 'created_at')


class ApprovalNodeInline(admin.TabularInline):
	model = ApprovalNode
	extra = 0
	readonly_fields = ('created_at', 'approved_at')


@admin.register(ApprovalFlow)
class ApprovalFlowAdmin(admin.ModelAdmin):
	list_display = ('packing_list', 'current_node', 'status', 'updated_at')
	list_filter = ('status', 'current_node')
	inlines = (ApprovalNodeInline,)
