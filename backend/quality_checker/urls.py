from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import QualityCheckTaskViewSet, QualityStandardViewSet

router = DefaultRouter()
router.register(r'tasks', QualityCheckTaskViewSet, basename='quality-task')
router.register(r'standards', QualityStandardViewSet, basename='quality-standard')

urlpatterns = [
    path('', include(router.urls)),
]
