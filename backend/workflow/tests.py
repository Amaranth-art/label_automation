import tempfile
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import Department, UserProfile
from .models import ApprovalFlow, ApprovalNode, LabelApplication

User = get_user_model()


class ApprovalWorkflowApiTests(TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.media_settings = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.media_settings.enable()
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

    def tearDown(self):
        self.media_settings.disable()
        self.media_directory.cleanup()

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
        self.assertTrue(response.data["file_url"].startswith("/media/"))
        self.assertFalse(response.data["file_url"].startswith("http"))
        return response.data["id"]

    def upload_label_sample(self):
        self.authenticate("label")
        response = self.client.post(
            "/api/label-application/upload-sample/",
            {"files": SimpleUploadedFile("sample.png", b"png image bytes", content_type="image/png")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        uploaded_file = response.data["files"][0]
        self.assertEqual(uploaded_file["url"], f"/media/{uploaded_file['path']}")
        self.assertFalse(uploaded_file["url"].startswith("http"))
        return uploaded_file["path"]

    def test_new_model_flow_supports_rejection_and_label_resubmission(self):
        packing_list_id = self.upload_packing_list()
        sample_path = self.upload_label_sample()
        self.authenticate("label")
        response = self.client.post(
            "/api/label-application/",
            {
                "packing_list": packing_list_id,
                "is_new_model": True,
                "form_data": {"label_size": "50x30"},
                "label_sample_images": [sample_path],
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

    def test_label_application_accepts_form_payload_and_routes_by_print_type(self):
        packing_list_id = self.upload_packing_list()
        sample_path = self.upload_label_sample()
        self.authenticate("label")
        form_data = {
            "print_type": "new_model",
            "line": "A线",
            "group_leader": "张三",
            "printer": "李四",
            "fields": {"machine_type": "M-100", "quantity": 100},
            "remark": "更改说明",
            "manufacturing_manager": "王五",
        }
        response = self.client.post(
            "/api/label-application/",
            {
                "packing_list_id": packing_list_id,
                "form_data": form_data,
                "label_sample_images": [sample_path],
                "next_handler_id": self.users["engineering"].id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        application = LabelApplication.objects.get(packing_list_id=packing_list_id)
        self.assertEqual(application.form_data, form_data)
        self.assertTrue(application.is_new_model)
        self.assertEqual(ApprovalFlow.objects.get(packing_list_id=packing_list_id).current_node, "eng")

        response = self.client.get(
            f"/api/approval/flow/{ApprovalFlow.objects.get(packing_list_id=packing_list_id).id}/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["packing_list"]["file_name"], "packing.pdf")
        self.assertTrue(response.data["packing_list"]["file_url"].startswith("/media/"))
        self.assertFalse(response.data["packing_list"]["file_url"].startswith("http"))
        self.assertTrue(response.data["packing_list"]["file_url"].endswith(".pdf"))
        self.assertEqual(response.data["packing_list"]["file_type"], "pdf")
        self.assertEqual(response.data["label_application"]["form_data"], form_data)
        self.assertEqual(response.data["label_application"]["label_sample_images"][0]["path"], sample_path)
        self.assertEqual(
            response.data["label_application"]["label_sample_images"][0]["url"],
            f"/media/{sample_path}",
        )
        self.assertEqual(response.data["label_application"]["applicant"]["id"], self.users["label"].id)

    def test_packing_list_rejects_unsupported_extension_and_large_file(self):
        self.authenticate("business")
        for name, content, expected in (
            ("packing.gif", b"image", "File format not supported"),
            ("packing.pdf", b"x" * (10 * 1024 * 1024 + 1), "File size exceeds 10MB limit"),
        ):
            with self.subTest(name=name):
                response = self.client.post(
                    "/api/packing-list/",
                    {
                        "file": SimpleUploadedFile(name, content),
                        "machine_type": "M-100",
                        "order_no": f"ORDER-{name}",
                        "label_handler_id": self.users["label"].id,
                    },
                    format="multipart",
                    HTTP_ACCEPT_LANGUAGE="en",
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn(expected, str(response.data))

    def test_label_sample_upload_requires_images_and_rejects_invalid_files(self):
        packing_list_id = self.upload_packing_list()
        self.authenticate("label")
        empty_response = self.client.post("/api/label-application/upload-sample/", {}, format="multipart")
        self.assertEqual(empty_response.status_code, 400)

        invalid_response = self.client.post(
            "/api/label-application/upload-sample/",
            {"files": SimpleUploadedFile("sample.webp", b"image bytes")},
            format="multipart",
        )
        self.assertEqual(invalid_response.status_code, 400)
        self.assertIn("Only jpg, jpeg, png are allowed", str(invalid_response.data))

        oversized_response = self.client.post(
            "/api/label-application/upload-sample/",
            {"files": SimpleUploadedFile("sample.jpg", b"x" * (10 * 1024 * 1024 + 1))},
            format="multipart",
        )
        self.assertEqual(oversized_response.status_code, 400)
        self.assertIn("File size exceeds 10MB limit", str(oversized_response.data))

        missing_sample_response = self.client.post(
            "/api/label-application/",
            {
                "packing_list_id": packing_list_id,
                "form_data": {"print_type": "normal"},
                "next_handler_id": self.users["qc"].id,
            },
            format="json",
        )
        self.assertEqual(missing_sample_response.status_code, 400)
        self.assertIn("Please upload at least one Label sample image", str(missing_sample_response.data))

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
        sample_path = self.upload_label_sample()
        self.authenticate("label")
        response = self.client.post(
            "/api/label-application/",
            {
                "packing_list": packing_list_id,
                "is_new_model": False,
                "form_data": {},
                "label_sample_images": [sample_path],
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