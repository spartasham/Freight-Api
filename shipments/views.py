from django.core.cache import cache
from django.db.models import Count, Sum, F
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Shipment, CsvImport, Consolidation
from .serializers import (
    ShipmentSerializer, CsvImportSerializer, ConsolidationModelSerializer
)
from .tasks import process_csv
import csv, os
from .filters import ShipmentFilter

 
class ShipmentViewSet(viewsets.ModelViewSet):
    queryset         = Shipment.objects.all().select_related("carrier", "customer")
    serializer_class = ShipmentSerializer
    filterset_fields = ["status", "destination", "origin", "mode", "carrier"]
    filterset_class = ShipmentFilter

class CsvImportViewSet(mixins.RetrieveModelMixin,
                        mixins.CreateModelMixin,
                        viewsets.GenericViewSet):
    queryset         = CsvImport.objects.all()
    serializer_class = CsvImportSerializer
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        # 1️⃣ Save the uploaded file record
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        csv_import = serializer.save(status="PROCESSING")

        # 2️⃣ Count rows (cheap head count) and update total_rows
        #    We could stream or read in chunks to avoid memory blowup
        file_path = csv_import.file.path
        with open(file_path, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            total = max(sum(1 for _ in reader) - 1, 0)  # subtract header
        csv_import.total_rows = total
        csv_import.save(update_fields=["total_rows"])

        # 3️⃣ Enqueue the background job
        process_csv.delay(csv_import.id, csv_import.file.path)

        # 4️⃣ Return the import object
        headers = self.get_success_headers(serializer.data)
        return Response(
            CsvImportSerializer(csv_import).data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    @action(detail=True, methods=["get"])
    def progress(self, request, pk=None):
        obj = self.get_object()
        return Response({"processed": obj.processed_rows, "total": obj.total_rows})

class MetricsViewSet(viewsets.ViewSet):
    """
    GET /api/metrics → overall KPIs, carrier breakdown,
    volume by mode, shipments per day. Cached 30s.
    """
    CACHE_KEY     = "metrics_cache"
    CACHE_TIMEOUT = 30  # seconds

    def list(self, request):
        data = cache.get(self.CACHE_KEY)
        if data is None:
            qs = Shipment.objects

            # 1️⃣ Counts by status
            counts = list(qs.values("status").annotate(total=Count("shipment_id")))

            # 2️⃣ Warehouse utilisation %
            total_vol = qs.aggregate(vol=Sum("volume"))["vol"] or 0
            utilisation = round(total_vol / 60_000_000_000 * 100, 2)

            # 3️⃣ Shipments by carrier
            by_carrier = list(
                qs.values(name=F("carrier__name"))
                  .annotate(total=Count("shipment_id"))
                  .order_by("-total")
            )

            # 4️⃣ Volume by mode (air vs sea)
            volume_by_mode = list(
                qs.values("mode")
                  .annotate(total_volume=Sum("volume"))
                  .order_by("mode")
            )

            # 5️⃣ Shipments per day (by arrival_date)
            shipments_per_day = list(
                qs.values(date=F("arrival_date"))
                  .annotate(count=Count("shipment_id"))
                  .order_by("date")
            )

            data = {
                "counts":              counts,
                "utilisation_pct":     utilisation,
                "by_carrier":          by_carrier,
                "volume_by_mode":      volume_by_mode,
                "shipments_per_day":   shipments_per_day,
            }
            cache.set(self.CACHE_KEY, data, self.CACHE_TIMEOUT)

        return Response(data)
    
class ConsolidationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Lists the saved consolidations and their linked shipments.
    """
    queryset         = Consolidation.objects.prefetch_related("consolidationshipment_set")
    serializer_class = ConsolidationModelSerializer
