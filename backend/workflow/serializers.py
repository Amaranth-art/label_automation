import os

from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from accounts.models import UserProfile
from accounts.serializers import UserSummarySerializer

from .models import ApprovalFlow, ApprovalNode, LabelApplication, PackingList

User = get_user_model()
STAGE_DEPARTMENTS = {
    ApprovalNode.Stage.LABEL_APPLY: {"label", "label_room"},
    ApprovalNode.Stage.ENGINEERING: {"eng", "engineering"},
    ApprovalNode.Stage.QC: {"qc"},
    ApprovalNode.Stage.IE: {"ie"},
    ApprovalNode.Stage.LABEL_CLOSE: {"label", "label_room"},
}
PACKING_LIST_EXTENSIONS = {".jpg", ".jpeg", ".png", ".doc", ".docx", ".pdf"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024


def user_is_in_stage_department(user, stage):
    try:
        return user.profile.department.code.lower() in STAGE_DEPARTMENTS[stage]
    except (KeyError, UserProfile.DoesNotExist, AttributeError):
        return False


class PackingListSerializer(serializers.ModelSerializer):
    uploader = UserSummarySerializer(read_only=True)
    file_name = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    file_type = serializers.SerializerMethodField()
    label_handler_id = serializers.PrimaryKeyRelatedField(
        source="label_handler", queryset=User.objects.filter(is_active=True), write_only=True
    )
    current_node = serializers.CharField(source="approval_flow.current_node", read_only=True)
    flow_status = serializers.CharField(source="approval_flow.status", read_only=True)

    class Meta:
        model = PackingList
        fields = (
            "id", "uploader", "file", "file_name", "file_url", "file_type",
            "machine_type", "order_no", "created_at",
            "status", "label_handler_id", "current_node", "flow_status",
        )
        read_only_fields = ("id", "uploader", "created_at", "status", "current_node", "flow_status")

    def validate_label_handler(self, user):
        if not user_is_in_stage_department(user, ApprovalNode.Stage.LABEL_APPLY):
            raise serializers.ValidationError(_("The initial handler must belong to the Label department."))
        return user

    def get_file_name(self, packing_list):
        return os.path.basename(packing_list.file.name)

    def get_file_url(self, packing_list):
        if not packing_list.file:
            return ""
        return packing_list.file.url

    def get_file_type(self, packing_list):
        return os.path.splitext(packing_list.file.name)[1].lower().lstrip(".")

    def validate_file(self, uploaded_file):
        extension = os.path.splitext(uploaded_file.name)[1].lower()
        if extension not in PACKING_LIST_EXTENSIONS:
            raise serializers.ValidationError(
                _("File format not supported. Allowed: jpg, jpeg, png, doc, docx, pdf")
            )
        if uploaded_file.size > MAX_UPLOAD_SIZE:
            raise serializers.ValidationError(_("File size exceeds 10MB limit"))
        return uploaded_file

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.is_staff:
            try:
                department_code = user.profile.department.code.lower()
            except UserProfile.DoesNotExist:
                raise serializers.ValidationError(_("Your account has no department profile.")) from None
            if department_code not in {"business", "biz"}:
                raise serializers.ValidationError(_("Only Business department users can upload packing lists."))
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        handler = validated_data.pop("label_handler")
        packing_list = PackingList.objects.create(uploader=self.context["request"].user, **validated_data)
        flow = ApprovalFlow.objects.create(packing_list=packing_list)
        ApprovalNode.objects.create(flow=flow, stage=ApprovalNode.Stage.LABEL_APPLY, handler=handler)
        return packing_list


class LabelApplicationSerializer(serializers.ModelSerializer):
    packing_list = serializers.PrimaryKeyRelatedField(
        queryset=PackingList.objects.all(), required=False, write_only=True
    )
    packing_list_id = serializers.PrimaryKeyRelatedField(
        source="packing_list", queryset=PackingList.objects.all(), required=False, write_only=True
    )
    is_new_model = serializers.BooleanField(required=False, write_only=True)
    label_sample_images = serializers.ListField(
        child=serializers.CharField(max_length=500),
        required=False,
        write_only=True,
    )
    next_handler_id = serializers.PrimaryKeyRelatedField(
        source="next_handler", queryset=User.objects.filter(is_active=True), write_only=True
    )

    class Meta:
        model = LabelApplication
        fields = (
            "id", "packing_list", "packing_list_id", "applicant", "is_new_model",
            "form_data", "label_sample_images", "created_at", "next_handler_id",
        )
        read_only_fields = ("id", "applicant", "created_at")

    def validate_form_data(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(_("Application form data must be an object."))
        print_type = value.get("print_type")
        if print_type is not None and print_type not in {"new_model", "normal", "rework", "repair"}:
            raise serializers.ValidationError({"print_type": _("Select a valid print type.")})
        return value

    def validate_label_sample_images(self, paths):
        for path in paths:
            normalized_path = path.replace("\\", "/")
            if not normalized_path.startswith("label-samples/") or ".." in normalized_path.split("/"):
                raise serializers.ValidationError(_("Invalid Label sample image path."))
            extension = os.path.splitext(normalized_path)[1].lower()
            if extension not in {".jpg", ".jpeg", ".png"}:
                raise serializers.ValidationError(_("Only jpg, jpeg, png are allowed"))
        return paths

    def validate(self, attrs):
        packing_list = attrs.get("packing_list")
        if packing_list is None:
            raise serializers.ValidationError({"packing_list_id": _("A packing list is required.")})
        print_type = attrs.get("form_data", {}).get("print_type")
        sample_images = attrs.get("label_sample_images")
        if sample_images is None:
            sample_images = attrs.get("form_data", {}).get("label_sample_images", [])
        try:
            sample_images = self.validate_label_sample_images(sample_images)
        except serializers.ValidationError as error:
            raise serializers.ValidationError({"label_sample_images": error.detail}) from None
        if not sample_images:
            raise serializers.ValidationError(
                {"label_sample_images": _("Please upload at least one Label sample image")}
            )
        attrs["label_sample_images"] = sample_images
        is_new_model = print_type == "new_model" if print_type is not None else attrs.get("is_new_model", False)
        attrs["is_new_model"] = is_new_model
        handler = attrs["next_handler"]
        if not user_is_in_stage_department(self.context["request"].user, ApprovalNode.Stage.LABEL_APPLY):
            raise serializers.ValidationError(_("Only Label department users can submit applications."))
        next_stage = ApprovalNode.Stage.ENGINEERING if is_new_model else ApprovalNode.Stage.QC
        if not user_is_in_stage_department(handler, next_stage):
            raise serializers.ValidationError({"next_handler_id": _("The handler must belong to the next department.")})
        try:
            flow = packing_list.approval_flow
            node = flow.nodes.get(stage=ApprovalNode.Stage.LABEL_APPLY, status=ApprovalNode.Status.PENDING)
        except (ApprovalFlow.DoesNotExist, ApprovalNode.DoesNotExist):
            raise serializers.ValidationError({"packing_list": _("No pending Label application task exists.")}) from None
        if flow.current_node != ApprovalNode.Stage.LABEL_APPLY:
            raise serializers.ValidationError({"packing_list": _("The Label application task is not current.")})
        if node.handler_id and node.handler_id != self.context["request"].user.id:
            raise serializers.ValidationError({"packing_list": _("This Label task is assigned to another user.")})
        attrs["flow"] = flow
        attrs["node"] = node
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        next_handler = validated_data.pop("next_handler")
        flow = validated_data.pop("flow")
        node = validated_data.pop("node")
        packing_list = validated_data["packing_list"]
        application, _ = LabelApplication.objects.update_or_create(
            packing_list=packing_list,
            defaults={
                "applicant": self.context["request"].user,
                "is_new_model": validated_data["is_new_model"],
                "form_data": validated_data.get("form_data", {}),
                "label_sample_images": validated_data["label_sample_images"],
            },
        )
        node.actual_handler = self.context["request"].user
        node.status = ApprovalNode.Status.APPROVED
        node.approved_at = timezone.now()
        node.save(update_fields=("actual_handler", "status", "approved_at"))
        next_stage = ApprovalNode.Stage.ENGINEERING if application.is_new_model else ApprovalNode.Stage.QC
        ApprovalNode.objects.create(flow=flow, stage=next_stage, handler=next_handler)
        flow.current_node = next_stage
        flow.status = ApprovalFlow.Status.PROCESSING
        flow.save(update_fields=("current_node", "status", "updated_at"))
        packing_list.status = PackingList.Status.PROCESSING
        packing_list.save(update_fields=("status",))
        return application


class ApprovalNodeSerializer(serializers.ModelSerializer):
    handler = UserSummarySerializer(read_only=True)
    actual_handler = UserSummarySerializer(read_only=True)
    flow_id = serializers.IntegerField(read_only=True)
    order_no = serializers.CharField(source="flow.packing_list.order_no", read_only=True)
    machine_type = serializers.CharField(source="flow.packing_list.machine_type", read_only=True)

    class Meta:
        model = ApprovalNode
        fields = ("id", "flow_id", "order_no", "machine_type", "stage", "handler", "actual_handler", "status", "comment", "reject_to", "approved_at", "created_at")


class ApprovalFlowSerializer(serializers.ModelSerializer):
    packing_list = PackingListSerializer(read_only=True)
    nodes = ApprovalNodeSerializer(many=True, read_only=True)
    label_application = serializers.SerializerMethodField()

    def get_label_application(self, flow):
        try:
            application = flow.packing_list.label_application
        except LabelApplication.DoesNotExist:
            return None
        return {
            "applicant": UserSummarySerializer(application.applicant).data,
            "is_new_model": application.is_new_model,
            "form_data": application.form_data,
            "label_sample_images": [
                {
                    "path": path,
                    "url": f"{settings.MEDIA_URL}{path}",
                    "file_name": os.path.basename(path),
                }
                for path in application.label_sample_images
            ],
            "created_at": application.created_at,
        }

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        packing = instance.packing_list
        file_url = packing.file.url
        representation["packing_list"] = {
            **representation["packing_list"],
            "file_name": os.path.basename(packing.file.name),
            "file_url": file_url,
            "file_type": os.path.splitext(packing.file.name)[1].lower().lstrip("."),
        }
        return representation

    class Meta:
        model = ApprovalFlow
        fields = ("id", "packing_list", "label_application", "current_node", "status", "created_at", "updated_at", "nodes")


class ApproveSerializer(serializers.Serializer):
    next_handler_id = serializers.PrimaryKeyRelatedField(
        source="next_handler", queryset=User.objects.filter(is_active=True), required=False
    )
    comment = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    on_behalf_of = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)


class RejectSerializer(serializers.Serializer):
    reject_to = serializers.ChoiceField(choices=ApprovalNode.Stage.choices)
    reason = serializers.CharField(max_length=4000, allow_blank=False, trim_whitespace=True)
    on_behalf_of = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)