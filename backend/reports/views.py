from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import TestReport
from .serializers import TestReportSerializer


class ReportListView(generics.ListAPIView):
    """报告列表视图（通过执行记录关联实现数据隔离）"""
    permission_classes = [IsAuthenticated]
    serializer_class = TestReportSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return TestReport.objects.all()
        return TestReport.objects.filter(execution__started_by=user).order_by('-created_at')


class ReportDetailView(generics.RetrieveAPIView):
    """报告详情视图（通过执行记录关联实现数据隔离）"""
    serializer_class = TestReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return TestReport.objects.all()
        return TestReport.objects.filter(execution__started_by=user)
