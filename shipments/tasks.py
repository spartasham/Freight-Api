import os, csv
from celery import shared_task
from django.conf import settings
from django.db import connection, transaction
from django.db.models import Count, Sum
from .models import CsvImport, Shipment, Consolidation, ConsolidationShipment

@shared_task(bind=True)
def process_csv(self, import_id, file_path):
    imp = CsvImport.objects.get(pk=import_id)
    imp.status = "PROCESSING"
    imp.save(update_fields=["status"])

    # 1️⃣ Stream via COPY for speed; fall back to csv.reader if COPY fails
    try:
        with connection.cursor() as cur:
            cur.copy_expert(
                sql="""
                COPY shipments_shipment(
                    shipment_id, customer_id, origin, destination, weight, volume,
                    mode, carrier_id, status, arrival_date, departure_date, delivered_date
                )
                FROM STDIN WITH (FORMAT csv, HEADER true)
                """,
                file=open(file_path, "r"),
            )
    except Exception:
        # fallback: row-by-row insert
        with open(file_path, newline="") as f:
            reader = csv.DictReader(f)
            batch = []
            for row in reader:
                batch.append(Shipment(
                    shipment_id    = row["shipment_id"],
                    customer_id    = row["customer_id"] or None,
                    origin         = row["origin"],
                    destination    = row["destination"],
                    weight         = float(row["weight"] or 0),
                    volume         = float(row["volume"] or 0),
                    mode           = row["mode"],
                    carrier_id     = row["carrier"] or None,
                    status         = row["status"],
                    arrival_date   = row["arrival"] or None,
                    departure_date = row["departure"] or None,
                    delivered_date = row["delivered"] or None,
                ))
                if len(batch) >= 5000:
                    Shipment.objects.bulk_create(batch, ignore_conflicts=True)
                    batch.clear()
            if batch:
                Shipment.objects.bulk_create(batch, ignore_conflicts=True)

    # 2️⃣ Update processed_rows
    imp.processed_rows = imp.total_rows
    imp.status = "COMPLETED"
    imp.save(update_fields=["processed_rows", "status"])


@shared_task
def generate_consolidations():
    """
    Rebuilds the Consolidation and ConsolidationShipment tables:
      1. Deletes any existing records.
      2. Groups Shipment rows by (destination, departure_date) where count >= 2.
      3. Creates a Consolidation per group with total_weight & total_volume.
      4. Links each Shipment in the group via ConsolidationShipment.
    """
    with transaction.atomic():
        # 1️⃣ Clear out old consolidations
        ConsolidationShipment.objects.all().delete()
        Consolidation.objects.all().delete()

        # 2️⃣ Find all groups worth consolidating
        groups = (
            Shipment.objects
            .values("destination", "departure_date")
            .annotate(
                count=Count("shipment_id"),
                total_weight=Sum("weight"),
                total_volume=Sum("volume"),
            )
            .filter(count__gte=2)
        )

        # 3️⃣ Persist each consolidation and its links
        for g in groups:
            con = Consolidation.objects.create(
                destination    = g["destination"],
                departure_date = g["departure_date"],
                total_weight   = g["total_weight"],
                total_volume   = g["total_volume"],
            )
            # 4️⃣ Link the shipments
            shipment_ids = Shipment.objects.filter(
                destination=con.destination,
                departure_date=con.departure_date
            ).values_list("shipment_id", flat=True)

            cs_objs = [
                ConsolidationShipment(consolidation=con, shipment_id=shp_id)
                for shp_id in shipment_ids
            ]
            ConsolidationShipment.objects.bulk_create(cs_objs)

    return f"Generated {groups.count()} consolidations"
    
