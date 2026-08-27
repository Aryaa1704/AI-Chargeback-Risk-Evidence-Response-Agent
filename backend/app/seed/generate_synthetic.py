"""Deterministic synthetic chargeback data generation."""

from __future__ import annotations

import hashlib
import logging
import random
from decimal import Decimal
from typing import TypedDict

from faker import Faker
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.device import Device
from app.models.dispute import Dispute
from app.models.merchant import Merchant
from app.models.transaction import Transaction

logger = logging.getLogger(__name__)

SYNTHETIC_SEED = 20260822
CUSTOMER_COUNT = 100
DEVICE_COUNT = 42
TRANSACTION_COUNT = 260
MERCHANT_COUNT = 18
DB_PREFIX = "synthetic_phase2"

COUNTRIES = ["IN", "US", "GB", "SG", "AE"]
CURRENCIES_BY_COUNTRY = {"IN": "INR", "US": "USD", "GB": "GBP", "SG": "SGD", "AE": "AED"}
NORMAL_STATUSES = ["captured", "authorized", "settled"]
MERCHANT_CATEGORIES = ["digital_goods", "travel", "food_delivery", "electronics", "gaming"]
DISPUTE_REASONS = ["fraudulent", "product_not_received", "duplicate", "credit_not_processed"]


class SeedSummary(TypedDict):
    customers: int
    transactions: int
    disputes: int
    devices: int


def _demo_id(entity: str, slug: str) -> str:
    digest = hashlib.sha256(f"{DB_PREFIX}.demo.{entity}.{slug}".encode()).hexdigest()
    return f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"


def _stable_id(entity: str, index: int) -> str:
    digest = hashlib.sha256(f"{DB_PREFIX}.{entity}.{index}".encode()).hexdigest()
    return f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"



def _add_curated_demo_cases(
    db: Session,
    customers: list[Customer],
    merchants: list[Merchant],
    devices: list[Device],
    transactions: list[Transaction],
    disputes: list[Dispute],
) -> None:
    """Append evaluator-friendly deterministic cases to the synthetic seed.

    The records below are still synthetic/demo data. They are intentionally
    named so reviewers can find a low, medium, high, and repeat-dispute example
    without relying on random Faker-generated values or fabricated evidence.
    """
    demo_customers = [
        Customer(id=_demo_id("customer", "low"), email="demo.low.risk@synthetic.example.test", full_name="Synthetic Low Risk Buyer", country="IN"),
        Customer(id=_demo_id("customer", "medium"), email="demo.medium.risk@synthetic.example.test", full_name="Synthetic Medium Risk Buyer", country="US"),
        Customer(id=_demo_id("customer", "high"), email="demo.high.risk@synthetic.example.test", full_name="Synthetic High Risk Buyer", country="GB"),
        Customer(id=_demo_id("customer", "repeat"), email="demo.repeat.disputes@synthetic.example.test", full_name="Synthetic Repeat Dispute Buyer", country="SG"),
    ]
    customers.extend(demo_customers)

    demo_merchants = [
        Merchant(id=_demo_id("merchant", "trusted"), name="synthetic_demo_trusted_books", category="digital_goods", country="IN"),
        Merchant(id=_demo_id("merchant", "travel"), name="synthetic_demo_travel_plus", category="travel", country="US"),
        Merchant(id=_demo_id("merchant", "electronics"), name="synthetic_demo_cross_border_electronics", category="electronics", country="AE"),
        Merchant(id=_demo_id("merchant", "gaming"), name="synthetic_demo_instant_gaming", category="gaming", country="AE"),
    ]
    merchants.extend(demo_merchants)

    demo_devices = [
        Device(id=_demo_id("device", "low"), customer_id=demo_customers[0].id, fingerprint="synthetic_demo_low_known_device", ip_address="10.10.1.11", user_agent="SyntheticDemo/low-risk"),
        Device(id=_demo_id("device", "medium"), customer_id=demo_customers[1].id, fingerprint="synthetic_demo_medium_device", ip_address="10.20.2.22", user_agent="SyntheticDemo/medium-risk"),
        Device(id=_demo_id("device", "high"), customer_id=demo_customers[2].id, fingerprint="synthetic_demo_high_new_device", ip_address="10.30.3.33", user_agent="SyntheticDemo/high-risk"),
        Device(id=_demo_id("device", "repeat"), customer_id=demo_customers[3].id, fingerprint="synthetic_demo_repeat_dispute_device", ip_address="10.40.4.44", user_agent="SyntheticDemo/repeat-dispute"),
    ]
    devices.extend(demo_devices)

    demo_transactions = [
        Transaction(id=_demo_id("transaction", "low"), transaction_id="TX-DEMO-LOW-001", customer_id=demo_customers[0].id, merchant_id=demo_merchants[0].id, device_id=demo_devices[0].id, amount=Decimal("18.99"), currency="INR", status="settled"),
        Transaction(id=_demo_id("transaction", "medium"), transaction_id="TX-DEMO-MED-001", customer_id=demo_customers[1].id, merchant_id=demo_merchants[1].id, device_id=demo_devices[1].id, amount=Decimal("182.40"), currency="USD", status="captured"),
        Transaction(id=_demo_id("transaction", "high"), transaction_id="TX-DEMO-HIGH-001", customer_id=demo_customers[2].id, merchant_id=demo_merchants[2].id, device_id=demo_devices[2].id, amount=Decimal("780.00"), currency="GBP", status="failed"),
        Transaction(id=_demo_id("transaction", "repeat-prior-a"), transaction_id="TX-DEMO-PRIOR-001", customer_id=demo_customers[3].id, merchant_id=demo_merchants[3].id, device_id=demo_devices[3].id, amount=Decimal("265.00"), currency="SGD", status="captured"),
        Transaction(id=_demo_id("transaction", "repeat-prior-b"), transaction_id="TX-DEMO-PRIOR-002", customer_id=demo_customers[3].id, merchant_id=demo_merchants[2].id, device_id=demo_devices[3].id, amount=Decimal("410.00"), currency="SGD", status="failed"),
        Transaction(id=_demo_id("transaction", "repeat-current"), transaction_id="TX-DEMO-REPEAT-001", customer_id=demo_customers[3].id, merchant_id=demo_merchants[3].id, device_id=demo_devices[3].id, amount=Decimal("690.00"), currency="SGD", status="failed"),
        Transaction(id=_demo_id("transaction", "hero"), transaction_id="TX-DEMO-001", customer_id=demo_customers[3].id, merchant_id=demo_merchants[2].id, device_id=demo_devices[3].id, amount=Decimal("1240.00"), currency="SGD", status="failed"),
    ]
    transactions.extend(demo_transactions)

    demo_disputes = [
        Dispute(id=_demo_id("dispute", "high"), transaction_id=demo_transactions[2].id, customer_id=demo_transactions[2].customer_id, reason_code="synthetic_demo_fraudulent", status="open", evidence_summary="Synthetic high-risk demo dispute. Not real customer, transaction, or evidence data."),
        Dispute(id=_demo_id("dispute", "repeat-prior-a"), transaction_id=demo_transactions[3].id, customer_id=demo_transactions[3].customer_id, reason_code="synthetic_demo_product_not_received", status="lost", evidence_summary="Synthetic prior dispute for repeat-dispute demo customer."),
        Dispute(id=_demo_id("dispute", "repeat-prior-b"), transaction_id=demo_transactions[4].id, customer_id=demo_transactions[4].customer_id, reason_code="synthetic_demo_credit_not_processed", status="under_review", evidence_summary="Synthetic prior refund-like dispute for repeat-dispute demo customer."),
        Dispute(id=_demo_id("dispute", "hero"), transaction_id=demo_transactions[6].id, customer_id=demo_transactions[6].customer_id, reason_code="synthetic_demo_fraudulent", status="open", evidence_summary="Synthetic hero demo dispute with high amount, failed status, cross-border merchant, and prior customer disputes."),
    ]
    disputes.extend(demo_disputes)


def _upsert_all(db: Session, records: list[object]) -> None:
    """Persist deterministic seed rows by their stable primary keys.

    The seed dataset owns these IDs, so merging them updates an earlier version
    of the same synthetic row while leaving every unrelated row untouched.
    """
    for record in records:
        db.merge(record)


def seed_synthetic(db: Session) -> SeedSummary:
    fake = Faker()
    Faker.seed(SYNTHETIC_SEED)
    rng = random.Random(SYNTHETIC_SEED)

    customers: list[Customer] = []
    for index in range(CUSTOMER_COUNT):
        country = COUNTRIES[index % len(COUNTRIES)]
        first = fake.first_name()
        last = fake.last_name()
        customers.append(Customer(
            id=_stable_id("customer", index),
            email=f"{DB_PREFIX}.{first.lower()}.{last.lower()}.{index}@synthetic.example.test",
            full_name=f"{first} {last}",
            country=country,
        ))

    merchants: list[Merchant] = []
    for index in range(MERCHANT_COUNT):
        merchants.append(Merchant(
            id=_stable_id("merchant", index),
            name=f"{DB_PREFIX}_merchant_{index}",
            category=MERCHANT_CATEGORIES[index % len(MERCHANT_CATEGORIES)],
            country=COUNTRIES[index % len(COUNTRIES)],
        ))

    devices: list[Device] = []
    for index in range(DEVICE_COUNT):
        customer = customers[index % len(customers)]
        devices.append(Device(
            id=_stable_id("device", index),
            customer_id=customer.id,
            fingerprint=f"{DB_PREFIX}_fp_{index}_{rng.randint(1000,9999)}",
            ip_address=fake.ipv4(),
            user_agent=fake.user_agent(),
        ))

    high_risk_count = int(TRANSACTION_COUNT * 0.135)
    transactions: list[Transaction] = []
    high_risk_transactions: list[Transaction] = []

    for index in range(TRANSACTION_COUNT):
        is_high_risk = index < high_risk_count
        customer = customers[index % len(customers)]
        merchant = merchants[index % len(merchants)]
        device = devices[index % len(devices)]
        amount = Decimal(rng.randint(2500 if is_high_risk else 100, 50000 if is_high_risk else 10000)) / Decimal("100")
        t = Transaction(
            id=_stable_id("transaction", index),
            transaction_id=f"{DB_PREFIX}_txn_{index:04d}",
            customer_id=customer.id,
            merchant_id=merchant.id,
            device_id=device.id,
            amount=amount,
            currency=CURRENCIES_BY_COUNTRY.get(customer.country or "IN", "INR"),
            status=rng.choice(["captured", "failed"] if is_high_risk else NORMAL_STATUSES),
        )
        transactions.append(t)
        if is_high_risk:
            high_risk_transactions.append(t)

    disputes: list[Dispute] = []
    for index, txn in enumerate(high_risk_transactions):
        disputes.append(Dispute(
            id=_stable_id("dispute", index),
            transaction_id=txn.id,
            customer_id=txn.customer_id,
            reason_code=f"{DB_PREFIX}_{DISPUTE_REASONS[index % len(DISPUTE_REASONS)]}",
            status=rng.choice(["open", "under_review", "won", "lost"]),
            evidence_summary="Synthetic dispute. Not real customer, transaction, or evidence data.",
        ))
    _add_curated_demo_cases(db, customers, merchants, devices, transactions, disputes)
    _upsert_all(db, customers)
    _upsert_all(db, merchants)
    _upsert_all(db, devices)
    _upsert_all(db, transactions)
    _upsert_all(db, disputes)
    db.commit()

    counts: SeedSummary = {
        "customers": len(customers),
        "transactions": len(transactions),
        "disputes": len(disputes),
        "devices": len(devices),
    }
    logger.info("Seeded synthetic demo data: %s", counts)
    return counts
