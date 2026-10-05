from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Department, UserProfile
from .models import ApprovalFlow, ApprovalNode, LabelApplication

User = get_user_model()


class ApprovalWorkflowApiTests(TestCase):
    def setUp(self):
        self.departments = {
            code: Department.objects.create(name=name, name_zh=name_zh, code=code)
            for code, name, name_zh in (
                ("business", "Business", "业务端"),
                ("label", "Label Room", "Label室"),
                ("engineering", "Engineering", "工程"),
                ("qc", "Quality Control", "品管"),
                ("ie", "IE Manufacturing", "IE制造"),
            )
        }
        self.users = {
            code: self.create_user(code, department)
            for code, department in self.departments.items()
        }
        self.client = APIClient()

    def create_user(self, username, department):
        user = User.objects.create_user(username=username, password="test-password-123")
        UserProfile.objects.create(
            user=user,
            department=department,
            display_name=username.title(),
            role=UserProfile.Role.SUPERVISOR,
        )
        return user

    def authenticate(self, username):
        self.client.force_authenticate(self.users[username])

    def upload_packing_list(self):
        self.authenticate("business")
        response = self.client.post(
            "/api/packing-list/",
            {
                "file": SimpleUploadedFile("packing.pdf", b"packing list", content_type="application/pdf"),
                "machine_type": "M-100",
                "order_no": "ORDER-100",
                "label_handler_id": self.users["label"].id,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["id"]

    def test_new_model_flow_supports_rejection_and_label_resubmission(self):
        packing_list_id = self.upload_packing_list()
        self.authenticate("label")
        response = self.client.post(
            "/api/label-application/",
            {
                "packing_list": packing_list_id,
                "is_new_model": True,
                "form_data": {"label_size": "50x30"},
                "next_handler_id": self.users["engineering"].id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(ApprovalFlow.objects.get(packing_list_id=packing_list_id).current_node, "eng")

        engineering_node = ApprovalNode.objects.get(
            flow__packing_list_id=packing_list_id, stage=ApprovalNode.Stage.ENGINEERING,
            status=ApprovalNode.Status.PENDING,
        )
        self.authenticate("engineering")
        response = self.client.post(
            f"/api/approval/{engineering_node.id}/approve/",
            {"next_handler_id": self.users["qc"].id},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

        qc_node = ApprovalNode.objects.get(
            flow__packing_list_id=packing_list_id, stage=ApprovalNode.Stage.QC,
            status=ApprovalNode.Status.PENDING,
        )
        self.authenticate("qc")
        response = self.client.post(
            f"/api/approval/{qc_node.id}/reject/",
            {"reject_to": ApprovalNode.Stage.ENGINEERING, "reason": "Please revise the drawing."},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["current_node"], ApprovalNode.Stage.ENGINEERING)

        rework_engineering = ApprovalNode.objects.filter(
            flow__packing_list_id=packing_list_id, stage=ApprovalNode.Stage.ENGINEERING,
            status=ApprovalNode.Status.PENDING,
        ).latest("created_at")
        self.authenticate("engineering")
        self.client.post(
            f"/api/approval/{rework_engineering.id}/approve/",
            {"next_handler_id": self.users["qc"].id},
            format="json",
        )
        qc_rework = ApprovalNode.objects.filter(
            flow__packing_list_id=packing_list_id, stage=ApprovalNode.Stage.QC,
            status=ApprovalNode.Status.PENDING,
        ).latest("created_at")
        self.authenticate("qc")
        self.client.post(
            f"/api/approval/{qc_rework.id}/approve/",
            {"next_handler_id": self.users["ie"].id},
            format="json",
        )
        ie_node = ApprovalNode.objects.get(
            flow__packing_list_id=packing_list_id, stage=ApprovalNode.Stage.IE,
            status=ApprovalNode.Status.PENDING,
        )
        self.authenticate("ie")
        self.client.post(
            f"/api/approval/{ie_node.id}/approve/",
            {"next_handler_id": self.users["label"].id},
            format="json",
        )
        close_node = ApprovalNode.objects.get(
            flow__packing_list_id=packing_list_id, stage=ApprovalNode.Stage.LABEL_CLOSE,
            status=ApprovalNode.Status.PENDING,
        )
        self.authenticate("label")
        self.client.post(f"/api/approval/{close_node.id}/approve/", {}, format="json")

        flow = ApprovalFlow.objects.get(packing_list_id=packing_list_id)
        self.assertEqual(flow.status, ApprovalFlow.Status.COMPLETED)
        self.assertEqual(flow.packing_list.status, "completed")
        self.assertEqual(LabelApplication.objects.get(packing_list_id=packing_list_id).form_data["label_size"], "50x30")

    def test_non_business_user_cannot_upload_packing_list(self):
        self.authenticate("qc")
        response = self.client.post(
            "/api/packing-list/",
            {
                "file": SimpleUploadedFile("packing.pdf", b"packing list"),
                "machine_type": "M-100",
                "order_no": "ORDER-200",
                "label_handler_id": self.users["label"].id,
            },
            format="multipart",
            HTTP_ACCEPT_LANGUAGE="zh-hans",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("只有业务端用户可以上传装箱单", str(response.data))

    def test_business_upload_error_defaults_to_english(self):
        self.authenticate("qc")
        response = self.client.post(
            "/api/packing-list/",
            {
                "file": SimpleUploadedFile("packing.pdf", b"packing list"),
                "machine_type": "M-100",
                "order_no": "ORDER-201",
                "label_handler_id": self.users["label"].id,
            },
            format="multipart",
            HTTP_ACCEPT_LANGUAGE="en",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Only Business department users can upload packing lists.", str(response.data))

    def test_department_directory_and_supervisor_delegation(self):
        qc_staff = User.objects.create_user(username="qc-staff", password="test-password-123")
        UserProfile.objects.create(
            user=qc_staff,
            department=self.departments["qc"],
            display_name="QC Staff",
            role=UserProfile.Role.STAFF,
            supervisor=self.users["qc"],
        )

        self.authenticate("label")
        response = self.client.get(
            "/api/users/",
            {"department": self.departments["qc"].id, "role": "staff"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([person["id"] for person in response.data], [qc_staff.id])

        packing_list_id = self.upload_packing_list()
        self.authenticate("label")
        response = self.client.post(
            "/api/label-application/",
            {
                "packing_list": packing_list_id,
                "is_new_model": False,
                "form_data": {},
                "next_handler_id": qc_staff.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)

        self.authenticate("qc")
        response = self.client.get("/api/approval/pending/?scope=department")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["handler"]["id"], qc_staff.id)
        node_id = response.data[0]["id"]
        response = self.client.post(
            f"/api/approval/{node_id}/approve/",
            {"on_behalf_of": qc_staff.id, "next_handler_id": self.users["ie"].id},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        handled_node = ApprovalNode.objects.get(pk=node_id)
        self.assertEqual(handled_node.handler_id, qc_staff.id)
        self.assertEqual(handled_node.actual_handler_id, self.users["qc"].id)