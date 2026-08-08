from django.urls import path
from .views import ReportListView, ReportDetailView

urlpatterns = [
    path('', ReportListView.as_view(), name='report_list'),
    path('<int:pk>/', ReportDetailView.as_view(), name='report_detail'),
]
