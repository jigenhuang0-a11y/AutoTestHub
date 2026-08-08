from django.urls import path
from . import views

urlpatterns = [
    # 性能测试用例 CRUD
    path('', views.PerfTestCaseViewSet.as_view({'get': 'list', 'post': 'create'}), name='perf-testcase-list'),
    path('<int:pk>/', views.PerfTestCaseViewSet.as_view({
        'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'
    }), name='perf-testcase-detail'),
    path('<int:pk>/executions/', views.PerfTestCaseViewSet.as_view({'get': 'executions'}), name='perf-testcase-executions'),

    # 执行相关
    path('execute/', views.PerfExecuteView.as_view(), name='perf-execute'),
    path('executions/', views.PerfExecutionListView.as_view(), name='perf-execution-list'),
    path('executions/<int:pk>/', views.PerfExecutionDetailView.as_view(), name='perf-execution-detail'),
    path('executions/<int:pk>/stop/', views.PerfExecutionStopView.as_view(), name='perf-execution-stop'),
    path('executions/<int:pk>/delete/', views.PerfExecutionDetailView.as_view(), name='perf-execution-delete'),
    path('executions/<int:pk>/metrics/', views.PerfExecutionMetricsView.as_view(), name='perf-execution-metrics'),
    path('executions/<int:pk>/diagnose/', views.PerfExecutionDiagnoseView.as_view(), name='perf-execution-diagnose'),
]
