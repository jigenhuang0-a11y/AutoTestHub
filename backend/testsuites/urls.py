from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import TestSuiteViewSet

router = SimpleRouter()
router.register(r'', TestSuiteViewSet, basename='testsuite')

urlpatterns = [
    path('', include(router.urls)),
]