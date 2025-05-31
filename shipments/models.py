from django.db import models
from django.utils import timezone

class CsvImport(models.Model):
    file           = models.FileField(upload_to="csv_imports/")
    file_name      = models.CharField(max_length=255)
    uploaded_at    = models.DateTimeField(default=timezone.now)
    status         = models.CharField(
        max_length=20,
        choices=[("PENDING","pending"),("PROCESSING","processing"),
                 ("ERROR","error"),("COMPLETED","completed")],
        default="PENDING",
    )
    total_rows     = models.PositiveBigIntegerField(default=0)
    processed_rows = models.PositiveBigIntegerField(default=0)
    error_log      = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if self.file and not self.file_name:
            self.file_name = self.file.name
        super().save(*args, **kwargs)

class Customer(models.Model):
    customer_id = models.CharField(max_length=32, primary_key=True)
    name        = models.CharField(max_length=120)
    email       = models.EmailField(blank=True)

class Carrier(models.Model):
    carrier_id = models.AutoField(primary_key=True)
    name       = models.CharField(max_length=120, unique=True)
    mode       = models.CharField(max_length=4, choices=[("air","air"),("sea","sea")])

class Shipment(models.Model):
    shipment_id   = models.CharField(max_length=40, primary_key=True)
    customer      = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    carrier       = models.ForeignKey(Carrier,  on_delete=models.SET_NULL, null=True, blank=True)
    origin        = models.CharField(max_length=2)   # US state
    destination   = models.CharField(max_length=3)   # Caribbean ISO
    weight        = models.FloatField()              # grams
    volume        = models.FloatField()              # cm³
    mode          = models.CharField(max_length=4, choices=[("air","air"),("sea","sea")])
    status        = models.CharField(
        max_length=12,
        choices=[("received","received"),("in-transit","in-transit"),("delivered","delivered")],
        default="received",
    )
    arrival_date    = models.DateField(null=True, blank=True)
    departure_date  = models.DateField(null=True, blank=True)
    delivered_date  = models.DateField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["destination", "departure_date"]),
        ]
        ordering = ["shipment_id"]

class Consolidation(models.Model):
    destination     = models.CharField(max_length=3)
    departure_date  = models.DateField()
    total_weight    = models.FloatField()
    total_volume    = models.FloatField()
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("destination", "departure_date")
        indexes = [models.Index(fields=["destination", "departure_date"])]
        ordering = ["destination", "departure_date"]

class ConsolidationShipment(models.Model):
    consolidation = models.ForeignKey(Consolidation, on_delete=models.CASCADE)
    shipment      = models.ForeignKey(Shipment,      on_delete=models.CASCADE)

    class Meta:
        unique_together = ("consolidation", "shipment")
