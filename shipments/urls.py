from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from shipments.views import ShipmentViewSet, CsvImportViewSet, MetricsViewSet, ConsolidationViewSet

router = DefaultRouter()
router.register("shipments",      ShipmentViewSet, basename="shipments")
router.register("imports",        CsvImportViewSet, basename="imports")
router.register("metrics",        MetricsViewSet,  basename="metrics")
router.register("consolidations", ConsolidationViewSet, basename="consolidations")

api_router = router
urlpatterns = [
    path("", include(api_router.urls)),
]
