from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import KnowledgeBaseViewSet, DocumentViewSet, ask_stream_view

router = DefaultRouter()
router.register(r'knowledge-bases', KnowledgeBaseViewSet, basename='knowledge-base')
router.register(r'documents', DocumentViewSet, basename='document')

urlpatterns = [
    path('knowledge-bases/<int:pk>/ask_stream/', ask_stream_view, name='knowledge-base-ask-stream'),
] + router.urls
