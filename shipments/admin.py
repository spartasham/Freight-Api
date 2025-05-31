from django.contrib import admin
from .models import Shipment, CsvImport, Consolidation


# Register your models here.
admin.site.register(Shipment)
admin.site.register(CsvImport)
admin.site.register(Consolidation)