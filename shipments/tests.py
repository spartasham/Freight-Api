from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from shipments.models import (
    Customer, Carrier, Shipment, CsvImport,
    Consolidation, ConsolidationShipment
)
from shipments.serializers import (
    ShipmentSerializer, CsvImportSerializer,
    ConsolidationModelSerializer
)
from shipments.tasks import generate_consolidations
import tempfile, os, csv

class ShipmentModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            customer_id="C1", name="TestCustomer", email="test@example.com"
        )
        self.carrier = Carrier.objects.create(name="TestCarrier", mode="air")

    def test_create_and_retrieve_shipment(self):
        shipment = Shipment.objects.create(
            shipment_id="S1",
            customer=self.customer,
            carrier=self.carrier,
            origin="NY",
            destination="JAM",
            weight=100.0,
            volume=50.0,
            mode="air",
            status="received",
            arrival_date="2025-01-01",
            departure_date="2025-01-02"
        )
        fetched = Shipment.objects.get(pk="S1")
        self.assertEqual(fetched.destination, "JAM")
        self.assertEqual(fetched.customer.email, "test@example.com")

class SerializerTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            customer_id="C2", name="Cust2", email="cust2@example.com"
        )
        self.carrier = Carrier.objects.create(name="Carrier2", mode="sea")
        self.shipment = Shipment.objects.create(
            shipment_id="S2",
            customer=self.customer,
            carrier=self.carrier,
            origin="CA",
            destination="BAR",
            weight=200.0,
            volume=150.0,
            mode="sea",
            status="delivered",
            arrival_date="2025-02-01",
            departure_date="2025-01-30",
            delivered_date="2025-02-02"
        )

    def test_shipment_serializer_fields(self):
        serializer = ShipmentSerializer(self.shipment)
        data = serializer.data
        self.assertEqual(data["shipment_id"], "S2")
        self.assertEqual(data["mode"], "sea")
        self.assertIn("arrival_date", data)

    def test_csvimport_serializer_read_only(self):
        csv_data = SimpleUploadedFile(
            "test.csv", b"shipment_id,customer_id,...\n", content_type="text/csv"
        )
        serializer = CsvImportSerializer(data={"file": csv_data})
        self.assertTrue(serializer.is_valid())
        self.assertNotIn("status", serializer.initial_data)

    def test_consolidation_model_serializer(self):
        # create a consolidation and linked shipments
        cons = Consolidation.objects.create(
            destination="TRI", departure_date="2025-03-01",
            total_weight=300.0, total_volume=250.0
        )
        Shipment.objects.create(
            shipment_id="S3", customer=self.customer, carrier=self.carrier,
            origin="FL", destination="TRI", weight=100.0, volume=80.0,
            mode="air", status="received",
            arrival_date="2025-03-02", departure_date="2025-03-01"
        )
        Shipment.objects.create(
            shipment_id="S4", customer=self.customer, carrier=self.carrier,
            origin="FL", destination="TRI", weight=200.0, volume=170.0,
            mode="air", status="received",
            arrival_date="2025-03-02", departure_date="2025-03-01"
        )
        # link shipments
        for shp in Shipment.objects.filter(destination="TRI"):
            ConsolidationShipment.objects.create(consolidation=cons, shipment=shp)
        # serialize
        serializer = ConsolidationModelSerializer(cons)
        data = serializer.data
        self.assertEqual(data["destination"], "TRI")
        self.assertEqual(len(data["shipments"]), 2)

class ConsolidationTaskTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            customer_id="C3", name="Cust3", email="c3@example.com"
        )
        self.carrier = Carrier.objects.create(name="Carrier3", mode="air")
        # create shipments in two groups
        for i in range(3):
            Shipment.objects.create(
                shipment_id=f"G1_{i}", customer=self.customer, carrier=self.carrier,
                origin="TX", destination="DOM", weight=10*(i+1), volume=5*(i+1),
                mode="air", status="received",
                arrival_date="2025-04-10", departure_date="2025-04-08"
            )
        # a single shipment not to be consolidated
        Shipment.objects.create(
            shipment_id="G2_0", customer=self.customer, carrier=self.carrier,
            origin="TX", destination="DOM", weight=50, volume=25,
            mode="sea", status="received",
            arrival_date="2025-04-15", departure_date="2025-04-13"
        )

    def test_generate_consolidations_creates_persisted(self):
        result = generate_consolidations.run()
        # only one group has count>=2
        self.assertEqual(Consolidation.objects.count(), 1)
        cons = Consolidation.objects.first()
        self.assertEqual(cons.destination, "DOM")
        self.assertEqual(cons.total_weight, 60.0)
        self.assertEqual(ConsolidationShipment.objects.filter(consolidation=cons).count(), 3)

class APITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = Customer.objects.create(
            customer_id="C4", name="Cust4", email="c4@example.com"
        )
        self.carrier = Carrier.objects.create(name="Carrier4", mode="sea")

    def test_import_and_progress_endpoints(self):
        # create a temp CSV file
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
        tmp.write(b"shipment_id,customer_id,origin,destination,weight,volume,mode,carrier,status,arrival,departure,delivered\n")
        tmp.write(b"X1,C4,CA,JAM,5,10,sea,1,received,2025-05-01,2025-04-30,\n")
        tmp.flush()
        tmp.close()

        with open(tmp.name, 'rb') as f:
            response = self.client.post(
                reverse('imports-list'), {'file': f}, format='multipart'
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        imp_id = response.data['id']

        # progress endpoint immediately
        resp2 = self.client.get(reverse('imports-progress', args=[imp_id]))
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertIn('processed', resp2.data)
        os.unlink(tmp.name)

    def test_shipments_list_and_detail(self):
        # seed a shipment
        shp = Shipment.objects.create(
            shipment_id="AP1", customer=self.customer, carrier=self.carrier,
            origin="MI", destination="BAR", weight=15, volume=20,
            mode="sea", status="in-transit",
            arrival_date="2025-06-01", departure_date="2025-05-30"
        )
        list_resp = self.client.get(reverse('shipments-list'))
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(list_resp.data['results'][0]['shipment_id'], "AP1")

        detail_resp = self.client.get(reverse('shipments-detail', args=["AP1"]))
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data['destination'], "BAR")

    def test_metrics_endpoint(self):
        # ensure at least one shipment
        Shipment.objects.create(
            shipment_id="M1", customer=self.customer, carrier=self.carrier,
            origin="CA", destination="JAM", weight=100, volume=200,
            mode="sea", status="delivered",
            arrival_date="2025-07-01", departure_date="2025-06-29"
        )
        met = self.client.get(reverse('metrics-list'))
        self.assertEqual(met.status_code, status.HTTP_200_OK)
        for key in ['counts', 'utilisation_pct', 'by_carrier', 'volume_by_mode', 'shipments_per_day']:
            self.assertIn(key, met.data)

    def test_consolidations_list_endpoint(self):
        # prepare two shipments in the same group
        for i in range(2):
            Shipment.objects.create(
                shipment_id=f"SC{i}",
                customer=self.customer,
                carrier=self.carrier,
                origin="TX",
                destination="BAR",
                weight=10*(i+1),
                volume=5*(i+1),
                mode="sea",
                status="received",
                arrival_date="2025-08-01",
                departure_date="2025-07-30"
            )

        # run the task to persist consolidations
        generate_consolidations.run()

        # hit the actual route you have registered
        resp = self.client.get(reverse('consolidations-list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.data['results'] if 'results' in resp.data else resp.data
        # we should have exactly 1 persisted consolidation
        self.assertEqual(len(data), 1)

        item = data[0]
        self.assertIn('id', item)
        self.assertEqual(item['destination'], 'BAR')
        # shipments should be a list of shipment_ids
        self.assertListEqual(sorted(item['shipments']), ['SC0', 'SC1'])
