from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EvalTaskViewSet, AIModelConfigViewSet

router = DefaultRouter()
router.register(r'tasks', EvalTaskViewSet, basename='eval-task')
router.register(r'models', AIModelConfigViewSet, basename='ai-model-config')

urlpatterns = [
    path('', include(router.urls)),
]
