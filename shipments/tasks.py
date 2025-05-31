import os, csv
from celery import shared_task
from django.conf import settings
from django.db import connection, transaction
from django.db.models import Count, Sum
from .models import CsvImport, Shipment, Consolidation, ConsolidationShipment, Customer
from datetime import datetime

DATE_INPUT_FORMATS = ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d")

def parse_date(value: str | None):
    """
    Accept '07/01/2025', '01/07/2025', or '2025-07-01'.
    Return a python date or None.
    """
    if not value:
        return None
    for fmt in DATE_INPUT_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    # If none match, raise so you see the bad value
    raise ValueError(f"Unrecognised date format: {value!r}")

@shared_task(bind=True)
def process_csv(self, import_id, file_path):
    imp = CsvImport.objects.get(pk=import_id)
    imp.status = "PROCESSING"
    imp.save(update_fields=["status"])

    POSTGRES = connection.vendor == "postgresql"

    try:
        if POSTGRES:
            with connection.cursor() as cur, open(file_path, "r") as f:
                cur.copy_expert(
                    sql="""
                    COPY shipments_shipment(
                        shipment_id, customer_id, origin, destination, weight, volume,
                        mode, carrier, status,
                        arrival_date, departure_date, delivered_date
                    )
                    FROM STDIN WITH (FORMAT csv, HEADER true)
                    """,
                    file=f,
                )
            imp.processed_rows = imp.total_rows
        else:
            # SQLite or any DB without COPY ─ row-by-row bulk_create
            with open(file_path, newline="") as f:
                reader = csv.DictReader(f)
                batch, processed = [], 0

                for row in reader:
                    processed += 1
                    cust_pk = int(row["customer_id"]) if row["customer_id"] else None
                    customer = None
                    if cust_pk:
                        customer, _ = Customer.objects.get_or_create(pk=cust_pk)

                    batch.append(
                        Shipment(
                            shipment_id=row["shipment_id"],
                            customer=customer,
                            origin=row["origin"],
                            destination=row["destination"],
                            weight=float(row.get("weight") or 0),
                            volume=float(row.get("volume") or 0),
                            mode=row["mode"],
                            carrier=row.get("carrier") or None,
                            status=row["status"],
                            arrival_date=parse_date(row.get("arrival_date")),
                            departure_date=parse_date(row.get("departure_date")),
                            delivered_date=parse_date(row.get("delivered_date")),
                        )
                    )
                    if len(batch) >= 500:
                        Shipment.objects.bulk_create(batch, ignore_conflicts=True)
                        batch.clear()
                        CsvImport.objects.filter(pk=import_id).update(processed_rows=processed)

                if batch:
                    Shipment.objects.bulk_create(batch, ignore_conflicts=True)
                    CsvImport.objects.filter(pk=import_id).update(processed_rows=processed)

                imp.processed_rows = processed

    except Exception as exc:
        imp.status = "FAILED"
        imp.save(update_fields=["status"])
        raise exc      # so Celery marks the task failed

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
    
