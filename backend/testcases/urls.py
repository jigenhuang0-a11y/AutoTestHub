from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import TestCaseViewSet, AIGenerateView, AIParseInterfaceView

router = SimpleRouter()
router.register(r'', TestCaseViewSet, basename='testcase')

urlpatterns = [
    path('ai-generate/', AIGenerateView.as_view(), name='ai_generate'),
    path('ai-parse-interface/', AIParseInterfaceView.as_view(), name='ai_parse_interface'),
    path('', include(router.urls)),
]
