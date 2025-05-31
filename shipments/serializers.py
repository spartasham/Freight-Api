from rest_framework import serializers
from .models import Shipment, CsvImport, Consolidation, ConsolidationShipment

class ShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Shipment
        fields = "__all__"

class CsvImportSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CsvImport
        fields = ["id", "file", "file_name", "uploaded_at", "status", "processed_rows", "total_rows"]
        read_only_fields = ["file_name", "uploaded_at", "status", "processed_rows", "total_rows"]

class ConsolidationShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ConsolidationShipment
        fields = ["shipment_id"]  # or expand to full ShipmentSerializer via nested relationship

class ConsolidationModelSerializer(serializers.ModelSerializer):
    shipments = serializers.SerializerMethodField()

    class Meta:
        model  = Consolidation
        fields = [
            "id", "destination", "departure_date",
            "total_weight", "total_volume", "created_at", "shipments"
        ]

    def get_shipments(self, obj):
        # return a list of shipment IDs (or use a nested ShipmentSerializer)
        return obj.consolidationshipment_set.values_list("shipment_id", flat=True)
