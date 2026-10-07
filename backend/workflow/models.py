from django.conf import settings
from django.db import models


class PackingList(models.Model):
	class Status(models.TextChoices):
		PENDING = "pending", "Pending"
		PROCESSING = "processing", "Processing"
		CLOSING = "closing", "Closing"
		COMPLETED = "completed", "Completed"
		REJECTED = "rejected", "Rejected"

	uploader = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name="packing_lists",
	)
	file = models.FileField(upload_to="packing-lists/%Y/%m/")
	machine_type = models.CharField(max_length=120)
	order_no = models.CharField(max_length=120, db_index=True)
	created_at = models.DateTimeField(auto_now_add=True)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

	class Meta:
		ordering = ("-created_at",)

	def __str__(self):
		return f"{self.order_no} - {self.machine_type}"


class LabelApplication(models.Model):
	packing_list = models.OneToOneField(
		PackingList,
		on_delete=models.CASCADE,
		related_name="label_application",
	)
	applicant = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name="label_applications",
	)
	is_new_model = models.BooleanField(default=False)
	form_data = models.JSONField(default=dict, blank=True)
	label_sample_images = models.JSONField(default=list, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"Label application for {self.packing_list.order_no}"


class ApprovalFlow(models.Model):
	class Status(models.TextChoices):
		PENDING = "pending", "Pending"
		PROCESSING = "processing", "Processing"
		CLOSING = "closing", "Closing"
		COMPLETED = "completed", "Completed"
		REJECTED = "rejected", "Rejected"

	packing_list = models.OneToOneField(
		PackingList,
		on_delete=models.CASCADE,
		related_name="approval_flow",
	)
	current_node = models.CharField(max_length=30, default="label_apply")
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ("-created_at",)

	def __str__(self):
		return f"Flow {self.pk}: {self.packing_list.order_no}"


class ApprovalNode(models.Model):
	class Stage(models.TextChoices):
		LABEL_APPLY = "label_apply", "Label application"
		ENGINEERING = "eng", "Engineering"
		QC = "qc", "Quality control"
		IE = "ie", "IE manufacturing"
		LABEL_CLOSE = "label_close", "Label closing"

	class Status(models.TextChoices):
		PENDING = "pending", "Pending"
		APPROVED = "approved", "Approved"
		REJECTED = "rejected", "Rejected"

	flow = models.ForeignKey(ApprovalFlow, on_delete=models.CASCADE, related_name="nodes")
	stage = models.CharField(max_length=20, choices=Stage.choices)
	handler = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		null=True,
		blank=True,
		related_name="assigned_approval_nodes",
	)
	actual_handler = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		null=True,
		blank=True,
		related_name="handled_approval_nodes",
	)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
	comment = models.TextField(blank=True)
	reject_to = models.CharField(max_length=20, blank=True)
	approved_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ("created_at", "pk")

	def __str__(self):
		return f"{self.flow_id}: {self.get_stage_display()} ({self.get_status_display()})"
