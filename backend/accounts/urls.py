from rest_framework.routers import DefaultRouter

from .views import DepartmentViewSet, GroupViewSet, UserViewSet

router = DefaultRouter()
router.register('departments', DepartmentViewSet, basename='department')
router.register('groups', GroupViewSet, basename='group')
router.register('users', UserViewSet, basename='user')

urlpatterns = router.urls