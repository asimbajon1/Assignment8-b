# pylint: disable=no-self-use
from datetime import date
from unittest import mock
import pytest
from allocation.adapters import repository
from allocation.domain import commands, events
from allocation.service_layer import handlers, messagebus, unit_of_work


class FakeRepository(repository.AbstractRepository):
    def __init__(self, products):
        super().__init__()
        self._products = set(products)

    def _add(self, product):
        self._products.add(product)

    def _get(self, sku):
        return next((p for p in self._products if p.sku == sku), None)

    def _get_by_batchref(self, batchref):
        return next(
            (p for p in self._products for b in p.batches if b.reference == batchref),
            None,
        )


class FakeUnitOfWork(unit_of_work.AbstractUnitOfWork):
    def __init__(self):
        self.products = FakeRepository([])
        self.committed = False

    def _commit(self):
        self.committed = True

    def rollback(self):
        pass


class TestAddBatch:
    def test_for_new_product(self):
        uow = FakeUnitOfWork()
        messagebus.handle(
            commands.CreateBatch("b1", "SEABREEZE", 100, None), uow
        )
        assert uow.products.get("SEABREEZE") is not None
        assert uow.committed

    def test_for_existing_product(self):
        uow = FakeUnitOfWork()
        messagebus.handle(commands.CreateBatch("b1", "NIGHTCLUB", 100, None), uow)
        messagebus.handle(commands.CreateBatch("b2", "NIGHTCLUB", 99, None), uow)
        assert "b2" in [b.reference for b in uow.products.get("NIGHTCLUB").batches]


class TestAllocate:
    def test_allocates(self):
        uow = FakeUnitOfWork()
        messagebus.handle(
            commands.CreateBatch("batch1", "FOREST", 100, None), uow
        )
        results = messagebus.handle(
            commands.Allocate("o1", "FOREST", 10), uow
        )
        assert results.pop(0) == "batch1"
        [batch] = uow.products.get("FOREST").batches
        assert batch.available_quantity == 90

    def test_errors_for_invalid_sku(self):
        uow = FakeUnitOfWork()
        messagebus.handle(commands.CreateBatch("b1", "AREALSKU", 100, None), uow)

        with pytest.raises(handlers.InvalidSku, match="Invalid sku NONEXISTENTSKU"):
            messagebus.handle(commands.Allocate("o1", "NONEXISTENTSKU", 10), uow)

    def test_commits(self):
        uow = FakeUnitOfWork()
        messagebus.handle(
            commands.CreateBatch("b1", "JUNGLE", 100, None), uow
        )
        messagebus.handle(commands.Allocate("o1", "JUNGLE", 10), uow)
        assert uow.committed

    def test_sends_email_on_out_of_stock_error(self):
        uow = FakeUnitOfWork()
        messagebus.handle(
            commands.CreateBatch("b1", "BUSY-STREET", 9, None), uow
        )

        with mock.patch("allocation.adapters.email.send") as mock_send_mail:
            messagebus.handle(commands.Allocate("o1", "BUSY-STREET", 10), uow)
            assert mock_send_mail.call_args == mock.call(
                "stock@made.com", f"Out of stock for BUSY-STREET"
            )


class TestChangeBatchQuantity:
    def test_changes_available_quantity(self):
        uow = FakeUnitOfWork()
        messagebus.handle(
            commands.CreateBatch("batch1", "SEABREEZE", 100, None), uow
        )
        [batch] = uow.products.get(sku="SEABREEZE").batches
        assert batch.available_quantity == 100

        messagebus.handle(commands.ChangeBatchQuantity("batch1", 50), uow)

        assert batch.available_quantity == 50

    def test_reallocates_if_necessary(self):
        uow = FakeUnitOfWork()
        history = [
            commands.CreateBatch("batch1", "NIGHTCLUB", 50, None),
            commands.CreateBatch("batch2", "NIGHTCLUB", 50, date.today()),
            commands.Allocate("order1", "NIGHTCLUB", 20),
            commands.Allocate("order2", "NIGHTCLUB", 20),
        ]
        for msg in history:
            messagebus.handle(msg, uow)
        [batch1, batch2] = uow.products.get(sku="NIGHTCLUB").batches
        assert batch1.available_quantity == 10
        assert batch2.available_quantity == 50

        messagebus.handle(commands.ChangeBatchQuantity("batch1", 25), uow)

        # order1 or order2 will be deallocated, so we'll have 25 - 20
        assert batch1.available_quantity == 5
        # and 20 will be reallocated to the next batch
        assert batch2.available_quantity == 30
