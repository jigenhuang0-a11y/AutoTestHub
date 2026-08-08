from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DatasetViewSet, TemplateViewSet, UsageLogViewSet, PresetTemplateViewSet

router = DefaultRouter()
router.register(r'datasets', DatasetViewSet, basename='dataset')
router.register(r'templates', TemplateViewSet, basename='template')
router.register(r'usage-logs', UsageLogViewSet, basename='usage-log')
router.register(r'preset-templates', PresetTemplateViewSet, basename='preset-template')

urlpatterns = [
    path('', include(router.urls)),
]
