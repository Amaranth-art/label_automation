from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


User = get_user_model()


class ChangePasswordApiTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='password-user', password='initial-password')
		self.client = APIClient()
		self.client.force_authenticate(self.user)
		self.url = '/api/auth/change-password/'

	def test_rejects_wrong_old_password(self):
		response = self.client.post(self.url, {
			'old_password': 'wrong-password',
			'new_password': 'new-password',
			'confirm_password': 'new-password',
		}, format='json', HTTP_ACCEPT_LANGUAGE='zh-hans')

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.data['code'], 'old_password_wrong')
		self.assertEqual(response.data['detail'], '旧密码错误。')

	def test_rejects_mismatched_passwords(self):
		response = self.client.post(self.url, {
			'old_password': 'initial-password',
			'new_password': 'new-password',
			'confirm_password': 'different-password',
		}, format='json')

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.data['code'], 'not_match')

	def test_rejects_same_password(self):
		response = self.client.post(self.url, {
			'old_password': 'initial-password',
			'new_password': 'initial-password',
			'confirm_password': 'initial-password',
		}, format='json')

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.data['code'], 'same_as_old')

	def test_changes_password_and_accepts_simple_password(self):
		response = self.client.post(self.url, {
			'old_password': 'initial-password',
			'new_password': '123456',
			'confirm_password': '123456',
		}, format='json')

		self.assertEqual(response.status_code, 200)
		self.user.refresh_from_db()
		self.assertTrue(self.user.check_password('123456'))

	def test_requires_authentication(self):
		self.client.force_authenticate(user=None)
		response = self.client.post(self.url, {}, format='json')

		self.assertEqual(response.status_code, 401)
