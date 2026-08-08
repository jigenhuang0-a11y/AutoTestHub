from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import TestExecutionViewSet, serve_report_resource

router = SimpleRouter()
router.register(r'', TestExecutionViewSet, basename='execution')

urlpatterns = [
    path('', include(router.urls)),
    path('<int:execution_id>/report/<path:path>', serve_report_resource, name='report-resource'),
]
