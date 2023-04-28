from datetime import date, timedelta
from allocation.domain import events
from allocation.domain.model import Product, OrderLine, Batch


today = date.today()
tomorrow = today + timedelta(days=1)
later = tomorrow + timedelta(days=10)


def test_prefers_warehouse_batches_to_shipments():
    in_stock_batch = Batch("in-stock-batch", "SEABREEZE", 100, eta=None)
    shipment_batch = Batch("shipment-batch", "SEABREEZE", 100, eta=tomorrow)
    product = Product(sku="SEABREEZE", batches=[in_stock_batch, shipment_batch])
    line = OrderLine("oref", "SEABREEZE", 10)

    product.allocate(line)

    assert in_stock_batch.available_quantity == 90
    assert shipment_batch.available_quantity == 100


def test_prefers_earlier_batches():
    earliest = Batch("speedy-batch", "NIGHTCLUB", 100, eta=today)
    medium = Batch("normal-batch", "NIGHTCLUB", 100, eta=tomorrow)
    latest = Batch("slow-batch", "NIGHTCLUB", 100, eta=later)
    product = Product(sku="NIGHTCLUB", batches=[medium, earliest, latest])
    line = OrderLine("order1", "NIGHTCLUB", 10)

    product.allocate(line)

    assert earliest.available_quantity == 90
    assert medium.available_quantity == 100
    assert latest.available_quantity == 100


def test_returns_allocated_batch_ref():
    in_stock_batch = Batch("in-stock-batch-ref", "JUNGLE", 100, eta=None)
    shipment_batch = Batch("shipment-batch-ref", "JUNGLE", 100, eta=tomorrow)
    line = OrderLine("oref", "JUNGLE", 10)
    product = Product(sku="JUNGLE", batches=[in_stock_batch, shipment_batch])
    allocation = product.allocate(line)
    assert allocation == in_stock_batch.reference


def test_records_out_of_stock_event_if_cannot_allocate():
    batch = Batch("batch1", "FOREST", 10, eta=today)
    product = Product(sku="FOREST", batches=[batch])
    product.allocate(OrderLine("order1", "FOREST", 10))

    allocation = product.allocate(OrderLine("order2", "FOREST", 1))
    assert product.events[-1] == events.OutOfStock(sku="FOREST")
    assert allocation is None


def test_increments_version_number():
    line = OrderLine("oref", "BUSY-STREET", 10)
    product = Product(
        sku="BUSY-STREET", batches=[Batch("b1", "BUSY-STREET", 100, eta=None)]
    )
    product.version_number = 7
    product.allocate(line)
    assert product.version_number == 8
