import os
import uuid

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import UserProfile
from .models import ApprovalFlow, ApprovalNode, LabelApplication, PackingList
from .serializers import (
    ApprovalFlowSerializer,
    ApprovalNodeSerializer,
    ApproveSerializer,
    LabelApplicationSerializer,
    PackingListSerializer,
    RejectSerializer,
    STAGE_DEPARTMENTS,
    user_is_in_stage_department,
)

User = get_user_model()
NEXT_STAGE = {
    ApprovalNode.Stage.ENGINEERING: ApprovalNode.Stage.QC,
    ApprovalNode.Stage.QC: ApprovalNode.Stage.IE,
    ApprovalNode.Stage.IE: ApprovalNode.Stage.LABEL_CLOSE,
}
LABEL_SAMPLE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024


def profile_for(user):
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        raise PermissionDenied(_("Your account has no department profile.")) from None


def visible_flows(user):
    queryset = ApprovalFlow.objects.select_related("packing_list", "packing_list__uploader").prefetch_related(
        "nodes", "nodes__handler", "nodes__actual_handler"
    )
    if user.is_staff:
        return queryset
    profile = profile_for(user)
    visibility = Q(packing_list__uploader=user) | Q(nodes__handler=user) | Q(nodes__actual_handler=user)
    if profile.role == UserProfile.Role.SUPERVISOR:
        visibility |= Q(nodes__status=ApprovalNode.Status.PENDING, nodes__handler__profile__department=profile.department)
    return queryset.filter(visibility).distinct()


class PackingListListCreateView(generics.ListCreateAPIView):
    serializer_class = PackingListSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            queryset = PackingList.objects.select_related("uploader", "approval_flow").all()
        else:
            profile = profile_for(user)
            visibility = Q(uploader=user) | Q(approval_flow__nodes__handler=user) | Q(
                approval_flow__nodes__actual_handler=user
            )
            if profile.role == UserProfile.Role.SUPERVISOR:
                visibility |= Q(
                    approval_flow__nodes__status=ApprovalNode.Status.PENDING,
                    approval_flow__nodes__handler__profile__department=profile.department,
                )
            queryset = PackingList.objects.select_related("uploader", "approval_flow").filter(visibility).distinct()
        selected_status = self.request.query_params.get("status")
        if selected_status:
            queryset = queryset.filter(status=selected_status)
        selected_department = self.request.query_params.get("department")
        if selected_department:
            queryset = queryset.filter(
                approval_flow__nodes__handler__profile__department_id=selected_department
            ).distinct()
        return queryset


class PackingListDetailView(generics.RetrieveAPIView):
    serializer_class = PackingListSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return PackingList.objects.select_related("uploader", "approval_flow").filter(
            pk__in=visible_flows(self.request.user).values_list("packing_list_id", flat=True)
        )


class SubmitLabelApplicationView(generics.CreateAPIView):
    serializer_class = LabelApplicationSerializer
    permission_classes = (permissions.IsAuthenticated,)


class UploadLabelSampleView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        if not user_is_in_stage_department(request.user, ApprovalNode.Stage.LABEL_APPLY):
            raise PermissionDenied(_("Only Label department users can upload sample images."))
        if not ApprovalNode.objects.filter(
            handler=request.user,
            stage=ApprovalNode.Stage.LABEL_APPLY,
            status=ApprovalNode.Status.PENDING,
            flow__current_node=ApprovalNode.Stage.LABEL_APPLY,
        ).exists():
            raise PermissionDenied(_("No pending Label application task exists for this user."))

        uploaded_files = request.FILES.getlist("files")
        if not uploaded_files:
            raise ValidationError({"files": _("Please upload at least one Label sample image")})

        for uploaded_file in uploaded_files:
            extension = os.path.splitext(uploaded_file.name)[1].lower()
            if extension not in LABEL_SAMPLE_EXTENSIONS:
                raise ValidationError({"files": _("Only jpg, jpeg, png are allowed")})
            if uploaded_file.size > MAX_UPLOAD_SIZE:
                raise ValidationError({"files": _("File size exceeds 10MB limit")})

        saved_files = []
        for uploaded_file in uploaded_files:
            extension = os.path.splitext(uploaded_file.name)[1].lower()
            relative_path = (
                f"label-samples/{timezone.now():%Y/%m}/"
                f"{uuid.uuid4().hex}{extension}"
            )
            saved_path = default_storage.save(relative_path, uploaded_file)
            saved_files.append({
                "path": saved_path,
                "url": f"{settings.MEDIA_URL}{saved_path}",
                "file_name": os.path.basename(saved_path),
            })

        return Response({"files": saved_files}, status=status.HTTP_201_CREATED)


class PendingApprovalListView(generics.ListAPIView):
    serializer_class = ApprovalNodeSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        nodes = ApprovalNode.objects.filter(
            status=ApprovalNode.Status.PENDING,
            flow__current_node=F("stage"),
            flow__status__in=(ApprovalFlow.Status.PENDING, ApprovalFlow.Status.PROCESSING, ApprovalFlow.Status.CLOSING),
        ).select_related("flow__packing_list", "handler__profile__department")
        if user.is_staff:
            return nodes
        profile = profile_for(user)
        if self.request.query_params.get("scope") == "department":
            if profile.role != UserProfile.Role.SUPERVISOR:
                raise PermissionDenied(_("Only supervisors can view department-wide tasks."))
            nodes = nodes.filter(handler__profile__department=profile.department)
        else:
            nodes = nodes.filter(handler=user)
        return nodes.order_by("created_at")


class ApprovalNodeActionView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def _get_action_user(self, request, node, supplied_user):
        user = request.user
        if user.is_staff:
            return user
        profile = profile_for(user)
        if node.handler_id == user.id:
            if supplied_user and supplied_user.id != user.id:
                raise PermissionDenied(_("You cannot act on behalf of another user for your own task."))
            return user
        if profile.role != UserProfile.Role.SUPERVISOR:
            raise PermissionDenied(_("This approval task is assigned to another user."))
        if not supplied_user or supplied_user.id != node.handler_id:
            raise PermissionDenied(_("Select the assigned staff member when processing on their behalf."))
        if supplied_user.profile.supervisor_id != user.id:
            raise PermissionDenied(_("You can only act on behalf of your direct reports."))
        if supplied_user.profile.department_id != profile.department_id:
            raise PermissionDenied(_("The assigned user must belong to your department."))
        return user

    def post(self, request, node_id, action=None):
        is_reject = request.path.endswith("/reject/")
        serializer_class = RejectSerializer if is_reject else ApproveSerializer
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            node = get_object_or_404(
                ApprovalNode.objects.select_for_update().select_related(
                    "flow", "flow__packing_list", "handler__profile__department"
                ),
                pk=node_id,
            )
            if node.status != ApprovalNode.Status.PENDING or node.flow.current_node != node.stage:
                raise ValidationError(_("This approval task is no longer pending."))
            if node.stage == ApprovalNode.Stage.LABEL_APPLY:
                raise ValidationError(_("Submit the Label application to complete this task."))
            acting_user = self._get_action_user(request, node, data.get("on_behalf_of"))
            if is_reject:
                response_data = self._reject(node, acting_user, data)
            else:
                response_data = self._approve(node, acting_user, data)
        return Response(response_data, status=status.HTTP_200_OK)

    def _approve(self, node, acting_user, data):
        next_stage = NEXT_STAGE.get(node.stage)
        next_handler = data.get("next_handler")
        if next_stage:
            if not next_handler:
                raise ValidationError({"next_handler_id": _("A handler in the next department is required.")})
            if not user_is_in_stage_department(next_handler, next_stage):
                raise ValidationError({"next_handler_id": _("The handler must belong to the next department.")})
        node.status = ApprovalNode.Status.APPROVED
        node.actual_handler = acting_user
        node.comment = data.get("comment", "")
        node.approved_at = timezone.now()
        node.save(update_fields=("status", "actual_handler", "comment", "approved_at"))
        flow = node.flow
        packing_list = flow.packing_list
        if node.stage == ApprovalNode.Stage.LABEL_CLOSE:
            flow.status = ApprovalFlow.Status.COMPLETED
            packing_list.status = PackingList.Status.COMPLETED
        else:
            ApprovalNode.objects.create(flow=flow, stage=next_stage, handler=next_handler)
            flow.current_node = next_stage
            flow.status = (
                ApprovalFlow.Status.CLOSING
                if next_stage == ApprovalNode.Stage.LABEL_CLOSE
                else ApprovalFlow.Status.PROCESSING
            )
            packing_list.status = flow.status
        flow.save(update_fields=("current_node", "status", "updated_at"))
        packing_list.save(update_fields=("status",))
        return ApprovalFlowSerializer(flow).data

    def _reject(self, node, acting_user, data):
        reject_to = data["reject_to"]
        if reject_to == node.stage:
            raise ValidationError({"reject_to": _("Choose a previously completed stage.")})
        completed = node.flow.nodes.filter(stage=reject_to, status=ApprovalNode.Status.APPROVED).order_by("-created_at")
        target_node = completed.first()
        if target_node is None:
            raise ValidationError({"reject_to": _("The target stage must have been completed earlier in this flow.")})
        node.status = ApprovalNode.Status.REJECTED
        node.actual_handler = acting_user
        node.comment = data["reason"]
        node.reject_to = reject_to
        node.approved_at = timezone.now()
        node.save(update_fields=("status", "actual_handler", "comment", "reject_to", "approved_at"))
        handler = target_node.actual_handler or target_node.handler
        if handler is None:
            raise ValidationError({"reject_to": _("No previous handler is available for reassignment.")})
        flow = node.flow
        ApprovalNode.objects.create(flow=flow, stage=reject_to, handler=handler)
        flow.current_node = reject_to
        flow.status = (
            ApprovalFlow.Status.CLOSING
            if reject_to == ApprovalNode.Stage.LABEL_CLOSE
            else ApprovalFlow.Status.PROCESSING
        )
        flow.save(update_fields=("current_node", "status", "updated_at"))
        flow.packing_list.status = flow.status
        flow.packing_list.save(update_fields=("status",))
        return ApprovalFlowSerializer(flow).data


class ApprovalFlowDetailView(generics.RetrieveAPIView):
    serializer_class = ApprovalFlowSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_url_kwarg = "flow_id"

    def get_queryset(self):
        if self.request.user.is_staff:
            return visible_flows(self.request.user)
        return visible_flows(self.request.user)