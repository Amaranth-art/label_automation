from django.urls import path

from .views import (
    ApprovalFlowDetailView,
    ApprovalNodeActionView,
    PackingListDetailView,
    PackingListListCreateView,
    PendingApprovalListView,
    SubmitLabelApplicationView,
)

urlpatterns = [
    path('packing-list/', PackingListListCreateView.as_view(), name='packing-list-list'),
    path('packing-list/<int:pk>/', PackingListDetailView.as_view(), name='packing-list-detail'),
    path('label-application/', SubmitLabelApplicationView.as_view(), name='label-application'),
    path('approval/pending/', PendingApprovalListView.as_view(), name='approval-pending'),
    path('approval/<int:node_id>/approve/', ApprovalNodeActionView.as_view(), name='approval-approve'),
    path('approval/<int:node_id>/reject/', ApprovalNodeActionView.as_view(), name='approval-reject'),
    path('approval/flow/<int:flow_id>/', ApprovalFlowDetailView.as_view(), name='approval-flow-detail'),
]