from django.urls import path, re_path, include
from rest_framework.routers import SimpleRouter
from .views import WebTestCaseViewSet, WebTestExecutionListView, WebTestExecutionDetailView

router = SimpleRouter()
router.register(r'', WebTestCaseViewSet, basename='web_testcase')

# 用 re_path 确保 executions 路由优先于 router 的 <pk> 模式
urlpatterns = [
    re_path(r'^executions/$', WebTestExecutionListView.as_view(), name='web-test-executions'),
    re_path(r'^executions/(?P<pk>\d+)/$', WebTestExecutionDetailView.as_view(), name='web-test-execution-detail'),
    path('', include(router.urls)),
]
