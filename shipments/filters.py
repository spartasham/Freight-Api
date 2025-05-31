from django_filters import rest_framework as filters
from .models import Shipment

class ShipmentFilter(filters.FilterSet):
    departure_after  = filters.DateFilter(field_name="departure_date", lookup_expr="gte")
    departure_before = filters.DateFilter(field_name="departure_date", lookup_expr="lte")
    arrival_after    = filters.DateFilter(field_name="arrival_date",   lookup_expr="gte")
    arrival_before   = filters.DateFilter(field_name="arrival_date",   lookup_expr="lte")

    class Meta:
        model  = Shipment
        fields = [
            "status", "destination", "origin", "mode", "carrier",
            "departure_after", "departure_before", "arrival_after", "arrival_before",
        ]
