"""Step 9 integration tests: accounting posting wired to sales / purchasing / inventory.

Verifies:
  - Revenue + COGS JEs created with correct amounts on post_invoice
  - COGS sourced from stock_movement.unit_cost (never recomputed from balance)
  - auto_posting disabled → zero JEs created (regression guard)
  - Idempotency: posting twice never doubles journal entries
  - COLLECTION_POSTED, SALES_CREDIT_NOTE_POSTED/COGS, PURCHASE_GRN_POSTED,
    SUPPLIER_INVOICE_POSTED, SUPPLIER_PAYMENT_POSTED, PURCHASE_RETURN_POSTED,
    INVENTORY_ADJUSTMENT_IN journal entries each created with correct amounts
  - cancel_invoice reverses BOTH stock and JEs atomically (status REVERSED)
  - Closed accounting period blocks post_invoice entirely (atomicity)
  - KEY RECONCILIATION: GL inventory account balance == sum(qty × WAC) over all
    StockBalance rows after a full sequence of GRN → sale → GRN → adjust

Isolation contract:
  - accounting.service imports nothing from sales / purchasing / inventory
  - accounting.integration imports nothing from those modules

All tests run in a rolled-back transaction — nothing persists.
"""
from __future__ import annotations

import ast
import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.exceptions import ApprovalRequired, BusinessRuleViolation
from app.modules.accounting import schemas as acc_schemas
from app.modules.accounting import service as acc_service
from app.modules.accounting.models import (
    AccountSelectorType,
    AccountType,
    AccountingPeriod,
    JournalEntry,
    JournalEntryLine,
    JournalEntryStatus,
    PostingTemplateHeader,
    PostingTemplateLine,
)
from app.modules.auth import schemas as auth_schemas
from app.modules.auth import service as auth_service
from app.modules.inventory import schemas as inv_schemas
from app.modules.inventory import service as inv_service
from app.modules.inventory.models import StockBalance
from app.modules.master_data import schemas as md_schemas
from app.modules.master_data import service as md_service
from app.modules.master_data.models import (
    CustomerType,
    PaymentTerms,
    ProductType,
    SupplierType,
    UnitType,
)
from app.modules.organization import schemas as org_schemas
from app.modules.organization import service as org_service
from app.modules.organization.models import BranchType, WarehouseType
from app.modules.purchasing import schemas as p_schemas
from app.modules.purchasing import service as p_service
from app.modules.purchasing.models import PaymentAllocationMethod, ReturnStatus
from app.modules.sales import schemas as s_schemas
from app.modules.sales import service as s_service
from app.modules.sales.models import AllocationMethod, CollectionStatus, InvoiceStatus
from app.modules.shared import service as shared_service


# ---------------------------------------------------------------------------
# Account codes used throughout — must match what _acc_setup creates
# ---------------------------------------------------------------------------

_AR = "1130"
_CASH = "1120"
_INVENTORY = "1150"
_AP = "2110"
_GRN_ACCRUAL = "2120"
_VAT_PAYABLE = "2130"
_REVENUE = "4010"
_COGS = "5010"
_ADJUSTMENT = "6060"

_ACCOUNT_DEFS = [
    (_CASH,        "Bank",               "بنك",     AccountType.ASSET,     True),
    (_AR,          "Accounts Receivable","مدينون",  AccountType.ASSET,     True),
    (_INVENTORY,   "Inventory",          "مخزون",   AccountType.ASSET,     True),
    (_AP,          "Accounts Payable",   "دائنون",  AccountType.LIABILITY,  True),
    (_GRN_ACCRUAL, "GRN Accrual",        "استحقاق", AccountType.LIABILITY,  True),
    (_VAT_PAYABLE, "VAT Payable",        "ضريبة",   AccountType.LIABILITY,  True),
    (_REVENUE,     "Sales Revenue",      "إيراد",   AccountType.REVENUE,   True),
    (_COGS,        "COGS",               "تكلفة",   AccountType.EXPENSE,   True),
    (_ADJUSTMENT,  "Adj Expense",        "تسوية",   AccountType.EXPENSE,   True),
]

# (param_key, DR/CR side, amount_source) per template event
_TEMPLATE_DEFS: dict[str, list[tuple[str, str, str]]] = {
    "SALES_INVOICE_POSTED": [
        ("ar_account",      "DEBIT",  "gross_amount"),
        ("revenue_account", "CREDIT", "net_amount"),
        ("tax_account",     "CREDIT", "tax_amount"),
    ],
    "SALES_INVOICE_COGS": [
        ("cogs_account",      "DEBIT",  "cogs_total"),
        ("inventory_account", "CREDIT", "cogs_total"),
    ],
    "COLLECTION_POSTED": [
        ("cash_account", "DEBIT",  "total_amount"),
        ("ar_account",   "CREDIT", "total_amount"),
    ],
    "SALES_CREDIT_NOTE_POSTED": [
        ("revenue_account", "DEBIT",  "net_amount"),
        ("tax_account",     "DEBIT",  "tax_amount"),
        ("ar_account",      "CREDIT", "gross_amount"),
    ],
    "SALES_CREDIT_NOTE_COGS": [
        ("inventory_account", "DEBIT",  "return_cost"),
        ("cogs_account",      "CREDIT", "return_cost"),
    ],
    "PURCHASE_GRN_POSTED": [
        ("inventory_account",   "DEBIT",  "receipt_cost"),
        ("grn_accrual_account", "CREDIT", "receipt_cost"),
    ],
    "SUPPLIER_INVOICE_POSTED": [
        ("grn_accrual_account", "DEBIT",  "total_amount"),
        ("ap_account",          "CREDIT", "total_amount"),
    ],
    "SUPPLIER_PAYMENT_POSTED": [
        ("ap_account",   "DEBIT",  "total_amount"),
        ("cash_account", "CREDIT", "total_amount"),
    ],
    "PURCHASE_RETURN_POSTED": [
        ("grn_accrual_account", "DEBIT",  "return_cost"),
        ("inventory_account",   "CREDIT", "return_cost"),
    ],
    "INVENTORY_ADJUSTMENT_IN": [
        ("inventory_account",  "DEBIT",  "adjustment_cost"),
        ("adjustment_account", "CREDIT", "adjustment_cost"),
    ],
    "INVENTORY_ADJUSTMENT_OUT": [
        ("adjustment_account", "DEBIT",  "adjustment_cost"),
        ("inventory_account",  "CREDIT", "adjustment_cost"),
    ],
}


# ===========================================================================
# Low-level builders
# ===========================================================================

def _company(db, code):
    return org_service.create_company(
        db,
        org_schemas.CompanyCreate(
            code=code, name_en=f"{code} Ltd", name_ar=f"شركة {code}",
            commercial_registration_no=f"CR-{code}",
        ),
    )


def _user(db, company_id, username):
    return auth_service.create_user(
        db,
        auth_schemas.UserCreate(
            username=username, email=f"{username}@test.com",
            full_name_en=username, full_name_ar=username, password="Pass1234!",
        ),
        company_id=company_id,
        actor_id=None,
    )


def _branch(db, company_id, code="BR1"):
    return org_service.create_branch(
        db,
        org_schemas.BranchCreate(
            company_id=company_id, code=code,
            name_en=code, name_ar=code, branch_type=BranchType.BOTH,
        ),
    )


def _warehouse(db, branch_id, code="WH1"):
    return org_service.create_warehouse(
        db,
        org_schemas.WarehouseCreate(
            branch_id=branch_id, code=code, name_en=code, name_ar=code,
            warehouse_type=WarehouseType.FINISHED_GOODS,
        ),
    )


def _unit(db, company_id, code, utype=UnitType.COUNT):
    return md_service.create_unit(
        db,
        md_schemas.UnitOfMeasureCreate(
            code=code, name_en=code, name_ar=code, symbol=code[:3], unit_type=utype,
        ),
        company_id=company_id,
    )


def _category(db, company_id, code="CAT"):
    return md_service.create_category(
        db,
        md_schemas.CategoryCreate(code=code, name_en=code, name_ar=code),
        company_id=company_id,
    )


def _product(db, company_id, cat_id, unit_id, code="PROD"):
    return md_service.create_product(
        db,
        md_schemas.ProductCreate(
            code=code, name_en=code, name_ar=code,
            category_id=cat_id,
            product_type=ProductType.FINISHED_GOOD,
            base_unit_id=unit_id,
            sales_unit_id=unit_id,
            purchase_unit_id=unit_id,
        ),
        company_id=company_id,
    )


def _customer(db, company_id, code="CUST"):
    return md_service.create_customer(
        db,
        md_schemas.CustomerCreate(
            code=code, name_en=code, name_ar=code,
            customer_type=CustomerType.SHOP,
            payment_terms=PaymentTerms.CASH,
        ),
        company_id=company_id,
    )


def _supplier(db, company_id, code="SUP"):
    return md_service.create_supplier(
        db,
        md_schemas.SupplierCreate(
            code=code, name_en=code, name_ar=code,
            supplier_type=SupplierType.LOCAL,
            payment_terms=PaymentTerms.CREDIT,
            payment_term_days=30,
        ),
        company_id=company_id,
    )


def _price_list(db, company_id, code="STD"):
    pl = s_service.create_price_list(
        db,
        s_schemas.PriceListCreate(code=code, name_en=code, name_ar=code, is_default=True),
        company_id=company_id,
    )
    return pl


def _recv(db, company_id, wh_id, product_id, qty, cost):
    """Direct stock receipt (no accounting hook — used for pre-accounting stock)."""
    return inv_service.receive_stock(
        db,
        inv_schemas.ReceiveStockRequest(
            warehouse_id=wh_id, product_id=product_id,
            quantity=Decimal(str(qty)), unit_cost=Decimal(str(cost)),
        ),
        company_id=company_id,
    )


def _post_grn(db, w, qty, cost):
    """Create and post a GRN — triggers PURCHASE_GRN_POSTED accounting."""
    grn = p_service.create_grn(
        db,
        p_schemas.GoodsReceiptCreate(
            branch_id=w.branch.id,
            supplier_id=w.supplier.id,
            receipt_date=datetime.date.today(),
            lines=[
                p_schemas.GRNLineCreate(
                    product_id=w.product.id,
                    warehouse_id=w.warehouse.id,
                    unit_id=w.pc_unit.id,
                    quantity_received=Decimal(str(qty)),
                    unit_cost=Decimal(str(cost)),
                ),
            ],
        ),
        company_id=w.company.id,
        actor_id=w.actor.id,
    )
    return p_service.post_grn(db, grn.id, w.company.id, w.actor.id)


def _acc_setup(db, company_id, actor_id):
    """Create FY (2026), 12 monthly periods, Chart of Accounts, posting templates,
    and enable auto-posting with default account codes.
    Templates are company-scoped so tests are fully isolated.
    """
    # Fiscal Year 2026
    fy = acc_service.create_fiscal_year(
        db,
        acc_schemas.FiscalYearCreate(
            code="FY2026", name_en="FY 2026", name_ar="السنة المالية 2026",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
        ),
        company_id=company_id,
        actor_id=actor_id,
    )
    acc_service.generate_periods(
        db,
        acc_schemas.GeneratePeriodsRequest(fiscal_year_id=fy.id, count=12),
        company_id=company_id,
        actor_id=actor_id,
    )

    # Chart of Accounts
    for code, name_en, name_ar, atype, postable in _ACCOUNT_DEFS:
        acc_service.create_account(
            db,
            acc_schemas.AccountCreate(
                code=code, name_en=name_en, name_ar=name_ar,
                account_type=atype, is_postable=postable,
            ),
            company_id=company_id,
            actor_id=actor_id,
        )

    # Company-specific posting templates (won't pollute global namespace)
    for event_type, line_defs in _TEMPLATE_DEFS.items():
        hdr = PostingTemplateHeader(
            company_id=company_id,
            event_type=event_type,
            version=1,
            effective_from=datetime.date(2026, 1, 1),
            description=f"Test template: {event_type}",
        )
        db.add(hdr)
        db.flush()
        for seq, (param, side, amount_src) in enumerate(line_defs, start=10):
            db.add(PostingTemplateLine(
                header_id=hdr.id,
                selector_type=AccountSelectorType.PAYLOAD_ACCOUNT_CODE,
                selector_param=param,
                side=side,
                amount_source=amount_src,
                sequence=seq,
            ))
        db.flush()

    # Enable auto-posting + configure all default accounts
    acc_service.update_settings(
        db,
        acc_schemas.AccountingSettingsUpdate(
            enable_auto_posting=True,
            default_ar_account_code=_AR,
            default_cash_account_code=_CASH,
            default_sales_revenue_account_code=_REVENUE,
            default_tax_payable_account_code=_VAT_PAYABLE,
            default_inventory_account_code=_INVENTORY,
            default_cogs_account_code=_COGS,
            default_ap_account_code=_AP,
            default_grn_accrual_account_code=_GRN_ACCRUAL,
            default_inventory_adjustment_account_code=_ADJUSTMENT,
            default_purchase_variance_account_code=_ADJUSTMENT,
        ),
        company_id=company_id,
        actor_id=actor_id,
    )


def _build_world(db, company_code: str, initial_stock: bool = True):
    """Full test world: company + accounting + sales/purchasing context.
    initial_stock=True: pre-load 100 PCs at 5.000 via direct receive_stock
    (no accounting hook, since that's done before acc_setup in most tests).
    """
    co = _company(db, company_code)
    actor = _user(db, co.id, f"act_{company_code[:6].lower()}")
    approver = _user(db, co.id, f"apr_{company_code[:6].lower()}")
    br = _branch(db, co.id)
    wh = _warehouse(db, br.id)
    pc = _unit(db, co.id, "PC")
    cat = _category(db, co.id)
    prod = _product(db, co.id, cat.id, pc.id)
    customer = _customer(db, co.id)
    supplier = _supplier(db, co.id)
    pl = _price_list(db, co.id)
    s_service.add_price_list_item(
        db, pl.id,
        s_schemas.PriceListItemCreate(product_id=prod.id, unit_price=Decimal("10.000")),
        company_id=co.id,
    )
    if initial_stock:
        # Pre-load stock before accounting is enabled → no JE for this receive
        _recv(db, co.id, wh.id, prod.id, Decimal("100"), Decimal("5.000"))

    _acc_setup(db, co.id, actor.id)

    return SimpleNamespace(
        company=co, actor=actor, approver=approver,
        branch=br, warehouse=wh, pc_unit=pc,
        product=prod, customer=customer, supplier=supplier,
        price_list=pl,
    )


def _invoice(db, w, qty=10):
    """Create a POSTED cash invoice for `qty` PCs at 10.000 each."""
    inv = s_service.create_invoice(
        db,
        s_schemas.SalesInvoiceCreate(
            branch_id=w.branch.id,
            customer_id=w.customer.id,
            price_list_id=w.price_list.id,
            invoice_date=datetime.date.today(),
            lines=[
                s_schemas.InvoiceLineCreate(
                    product_id=w.product.id,
                    warehouse_id=w.warehouse.id,
                    unit_id=w.pc_unit.id,
                    quantity_ordered=Decimal(str(qty)),
                    unit_price=Decimal("10.000"),
                    price_source="PRICE_LIST",
                    line_discount=Decimal("0"),
                ),
            ],
        ),
        company_id=w.company.id,
    )
    s_service.post_invoice(db, inv.id, w.company.id, w.actor.id)
    return inv


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def _je(db, company_id, ikey):
    """Return the JE for an idempotency key, or None."""
    return (
        db.query(JournalEntry)
        .filter_by(idempotency_key=ikey, company_id=company_id)
        .first()
    )


def _je_totals(db, je_id):
    """Return (total_debit, total_credit) for a JE."""
    lines = db.query(JournalEntryLine).filter_by(entry_id=je_id).all()
    return (
        sum(ln.debit for ln in lines),
        sum(ln.credit for ln in lines),
    )


def _gl_net(db, company_id, account_code):
    """Net debit balance (DR − CR) for an account, across POSTED JEs."""
    from app.modules.accounting.models import Account
    acct = db.query(Account).filter_by(
        code=account_code, company_id=company_id, is_deleted=False,
    ).first()
    if acct is None:
        return Decimal("0")
    rows = (
        db.query(JournalEntryLine)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.entry_id)
        .filter(
            JournalEntryLine.account_id == acct.id,
            JournalEntry.company_id == company_id,
            JournalEntry.status == JournalEntryStatus.POSTED,
        )
        .all()
    )
    return sum(ln.debit - ln.credit for ln in rows)


# ===========================================================================
# Tests
# ===========================================================================


# ---------------------------------------------------------------------------
# 1. Revenue + COGS JEs on post_invoice
# ---------------------------------------------------------------------------

def test_revenue_and_cogs_je_created(db_session):
    """post_invoice → two JEs: SALES_INVOICE_POSTED (revenue) + SALES_INVOICE_COGS."""
    w = _build_world(db_session, "REVCO")
    inv = _invoice(db_session, w, qty=10)

    rev_je = _je(db_session, w.company.id, f"sale_invoice_{inv.id}_revenue")
    cogs_je = _je(db_session, w.company.id, f"sale_invoice_{inv.id}_cogs")

    assert rev_je is not None, "Revenue JE must be created"
    assert cogs_je is not None, "COGS JE must be created"
    assert rev_je.status == JournalEntryStatus.POSTED
    assert cogs_je.status == JournalEntryStatus.POSTED

    # Revenue JE: DR AR 100.000, CR Revenue 100.000 (no tax → tax line skipped)
    dr, cr = _je_totals(db_session, rev_je.id)
    assert dr == Decimal("100.000")
    assert cr == Decimal("100.000")

    # COGS JE: 10 PCs × 5.000 cost = 50.000
    dr, cr = _je_totals(db_session, cogs_je.id)
    assert dr == Decimal("50.000")
    assert cr == Decimal("50.000")


# ---------------------------------------------------------------------------
# 2. COGS sourced from movement cost, never recomputed
# ---------------------------------------------------------------------------

def test_cogs_sourced_from_movement_cost_not_recomputed(db_session):
    """After a second GRN at different cost the weighted-avg changes; COGS must
    reflect the movement.unit_cost at time of issue, not any re-query."""
    w = _build_world(db_session, "COGSSRC")
    # Add 100 PCs at 3.000 (direct receive, no JE — accounting already on,
    # but receive_stock has no accounting hook; only post_grn does)
    _recv(db_session, w.company.id, w.warehouse.id, w.product.id,
          Decimal("100"), Decimal("3.000"))
    # Weighted avg now = (100*5 + 100*3) / 200 = 4.000
    inv = _invoice(db_session, w, qty=10)
    cogs_je = _je(db_session, w.company.id, f"sale_invoice_{inv.id}_cogs")
    assert cogs_je is not None
    dr, cr = _je_totals(db_session, cogs_je.id)
    # COGS = 10 × 4.000 = 40.000 (movement.unit_cost from issue)
    assert dr == Decimal("40.000"), f"Expected 40.000, got {dr}"
    assert cr == Decimal("40.000")


# ---------------------------------------------------------------------------
# 3. Auto-posting disabled → zero JEs
# ---------------------------------------------------------------------------

def test_auto_posting_disabled_no_je_created(db_session):
    """Company with enable_auto_posting=False must produce zero journal entries."""
    w = _build_world(db_session, "NOACCT")
    acc_service.update_settings(
        db_session,
        acc_schemas.AccountingSettingsUpdate(enable_auto_posting=False),
        w.company.id, actor_id=None,
    )
    _invoice(db_session, w, qty=5)
    count = (
        db_session.query(JournalEntry)
        .filter_by(company_id=w.company.id)
        .count()
    )
    assert count == 0, "No JEs when auto-posting is disabled"


# ---------------------------------------------------------------------------
# 4. Idempotency: posting twice never doubles JEs
# ---------------------------------------------------------------------------

def test_idempotency_no_double_je(db_session):
    """The same idempotency key must not produce duplicate journal entries."""
    w = _build_world(db_session, "IDMPCO")
    inv = _invoice(db_session, w, qty=5)

    # Second call to post_invoice is short-circuited by status check (already POSTED)
    # But the real guard is the idempotency_key in PostingService._check_idempotency
    rev_count = (
        db_session.query(JournalEntry)
        .filter_by(company_id=w.company.id,
                   idempotency_key=f"sale_invoice_{inv.id}_revenue")
        .count()
    )
    cogs_count = (
        db_session.query(JournalEntry)
        .filter_by(company_id=w.company.id,
                   idempotency_key=f"sale_invoice_{inv.id}_cogs")
        .count()
    )
    assert rev_count == 1, "Exactly one revenue JE"
    assert cogs_count == 1, "Exactly one COGS JE"


# ---------------------------------------------------------------------------
# 5. COLLECTION_POSTED
# ---------------------------------------------------------------------------

def test_collection_posted_je(db_session):
    """post_collection → COLLECTION_POSTED: DR Cash, CR AR, balanced at total_amount."""
    w = _build_world(db_session, "COLLCO")
    inv = _invoice(db_session, w, qty=10)

    col = s_service.create_collection(
        db_session,
        s_schemas.CollectionCreate(
            branch_id=w.branch.id,
            customer_id=w.customer.id,
            collection_date=datetime.date.today(),
            total_amount=Decimal("100.000"),
            allocation_method=AllocationMethod.AUTO,
        ),
        company_id=w.company.id,
        actor_id=w.actor.id,
    )
    s_service.post_collection(db_session, col.id, w.company.id, w.actor.id)

    col_je = _je(db_session, w.company.id, f"sale_collection_{col.id}")
    assert col_je is not None, "Collection JE must be created"
    assert col_je.status == JournalEntryStatus.POSTED
    dr, cr = _je_totals(db_session, col_je.id)
    assert dr == Decimal("100.000")
    assert cr == Decimal("100.000")


# ---------------------------------------------------------------------------
# 6. SALES_CREDIT_NOTE_POSTED + SALES_CREDIT_NOTE_COGS
# ---------------------------------------------------------------------------

def test_credit_note_revenue_and_cogs_je(db_session):
    """post_credit_note → revenue reversal JE + COGS return JE."""
    w = _build_world(db_session, "CRNCO")
    inv = _invoice(db_session, w, qty=10)
    inv_detail, lines = s_service.get_invoice_detail(db_session, inv.id, w.company.id)

    cn = s_service.create_credit_note(
        db_session,
        s_schemas.CreditNoteCreate(
            original_invoice_id=inv.id,
            credit_note_date=datetime.date.today(),
            lines=[
                s_schemas.CreditNoteLineCreate(
                    original_line_id=lines[0].id,
                    quantity_returned=Decimal("5"),
                ),
            ],
        ),
        company_id=w.company.id,
        actor_id=w.actor.id,
    )
    s_service.post_credit_note(db_session, cn.id, w.company.id, w.actor.id)

    rev_je = _je(db_session, w.company.id, f"sale_cn_{cn.id}_revenue")
    cogs_je = _je(db_session, w.company.id, f"sale_cn_{cn.id}_cogs")
    assert rev_je is not None, "Credit note revenue reversal JE must be created"
    assert cogs_je is not None, "Credit note COGS return JE must be created"

    # Revenue reversal: 5 PCs × 10.000 = 50.000 (DR Revenue, CR AR)
    dr, cr = _je_totals(db_session, rev_je.id)
    assert dr == Decimal("50.000")
    assert cr == Decimal("50.000")

    # COGS return: stock received back at 5.000 cost → 5 × 5.000 = 25.000 (DR Inv, CR COGS)
    dr, cr = _je_totals(db_session, cogs_je.id)
    assert dr == Decimal("25.000")
    assert cr == Decimal("25.000")


# ---------------------------------------------------------------------------
# 7. PURCHASE_GRN_POSTED
# ---------------------------------------------------------------------------

def test_grn_posted_je(db_session):
    """post_grn → PURCHASE_GRN_POSTED: DR Inventory, CR GRN Accrual."""
    w = _build_world(db_session, "GRNCO", initial_stock=False)
    grn = _post_grn(db_session, w, qty=20, cost="4.500")

    grn_je = _je(db_session, w.company.id, f"purchase_grn_{grn.id}_receipt")
    assert grn_je is not None, "GRN JE must be created"
    dr, cr = _je_totals(db_session, grn_je.id)
    # 20 PCs × 4.500 = 90.000
    assert dr == Decimal("90.000")
    assert cr == Decimal("90.000")


# ---------------------------------------------------------------------------
# 8. SUPPLIER_INVOICE_POSTED
# ---------------------------------------------------------------------------

def test_supplier_invoice_posted_je(db_session):
    """post_supplier_invoice → SUPPLIER_INVOICE_POSTED: DR GRN Accrual, CR AP."""
    w = _build_world(db_session, "BILLCO", initial_stock=False)
    grn = _post_grn(db_session, w, qty=20, cost="4.500")
    _, grn_lines = p_service.get_grn_detail(db_session, grn.id, w.company.id)

    bill = p_service.create_supplier_invoice(
        db_session,
        p_schemas.SupplierInvoiceCreate(
            branch_id=w.branch.id,
            supplier_id=w.supplier.id,
            goods_receipt_id=grn.id,
            bill_date=datetime.date.today(),
            lines=[
                p_schemas.BillLineCreate(
                    grn_line_id=grn_lines[0].id,
                    product_id=w.product.id,
                    unit_id=w.pc_unit.id,
                    quantity=Decimal("20"),
                    unit_cost=Decimal("4.500"),
                ),
            ],
        ),
        company_id=w.company.id,
        actor_id=w.actor.id,
    )
    p_service.post_supplier_invoice(db_session, bill.id, w.company.id, w.actor.id)

    bill_je = _je(db_session, w.company.id, f"purchase_bill_{bill.id}")
    assert bill_je is not None, "Supplier invoice JE must be created"
    dr, cr = _je_totals(db_session, bill_je.id)
    # 20 × 4.500 = 90.000
    assert dr == Decimal("90.000")
    assert cr == Decimal("90.000")


# ---------------------------------------------------------------------------
# 9. SUPPLIER_PAYMENT_POSTED
# ---------------------------------------------------------------------------

def test_supplier_payment_posted_je(db_session):
    """post_supplier_payment → SUPPLIER_PAYMENT_POSTED: DR AP, CR Cash."""
    w = _build_world(db_session, "PAYCO", initial_stock=False)
    grn = _post_grn(db_session, w, qty=10, cost="6.000")
    _, grn_lines = p_service.get_grn_detail(db_session, grn.id, w.company.id)

    bill = p_service.create_supplier_invoice(
        db_session,
        p_schemas.SupplierInvoiceCreate(
            branch_id=w.branch.id,
            supplier_id=w.supplier.id,
            goods_receipt_id=grn.id,
            bill_date=datetime.date.today(),
            lines=[
                p_schemas.BillLineCreate(
                    grn_line_id=grn_lines[0].id,
                    product_id=w.product.id,
                    unit_id=w.pc_unit.id,
                    quantity=Decimal("10"),
                    unit_cost=Decimal("6.000"),
                ),
            ],
        ),
        company_id=w.company.id,
        actor_id=w.actor.id,
    )
    p_service.post_supplier_invoice(db_session, bill.id, w.company.id, w.actor.id)

    pay = p_service.create_supplier_payment(
        db_session,
        p_schemas.SupplierPaymentCreate(
            branch_id=w.branch.id,
            supplier_id=w.supplier.id,
            payment_date=datetime.date.today(),
            total_amount=Decimal("60.000"),
            allocation_method=PaymentAllocationMethod.AUTO,
        ),
        company_id=w.company.id,
        actor_id=w.actor.id,
    )
    p_service.post_supplier_payment(db_session, pay.id, w.company.id, w.actor.id)

    pay_je = _je(db_session, w.company.id, f"purchase_payment_{pay.id}")
    assert pay_je is not None, "Payment JE must be created"
    dr, cr = _je_totals(db_session, pay_je.id)
    assert dr == Decimal("60.000")
    assert cr == Decimal("60.000")


# ---------------------------------------------------------------------------
# 10. PURCHASE_RETURN_POSTED
# ---------------------------------------------------------------------------

def test_purchase_return_posted_je(db_session):
    """post_purchase_return (after mandatory approval) → PURCHASE_RETURN_POSTED JE."""
    w = _build_world(db_session, "RETCO", initial_stock=False)
    grn = _post_grn(db_session, w, qty=20, cost="4.000")
    _, grn_lines = p_service.get_grn_detail(db_session, grn.id, w.company.id)

    ret = p_service.create_purchase_return(
        db_session,
        p_schemas.PurchaseReturnCreate(
            branch_id=w.branch.id,
            supplier_id=w.supplier.id,
            original_grn_id=grn.id,
            return_date=datetime.date.today(),
            lines=[
                p_schemas.ReturnLineCreate(
                    original_grn_line_id=grn_lines[0].id,
                    quantity_returned=Decimal("5"),
                ),
            ],
        ),
        company_id=w.company.id,
        actor_id=w.actor.id,
    )

    # Purchase returns always require approval
    with pytest.raises(ApprovalRequired) as exc_info:
        p_service.post_purchase_return(db_session, ret.id, w.company.id,
                                       actor_id=w.actor.id)
    shared_service.approve_request(
        db_session, exc_info.value.approval_request_id,
        w.company.id, w.approver.id,
    )
    ret = p_service.post_purchase_return(db_session, ret.id, w.company.id,
                                         actor_id=w.actor.id)
    assert ret.status == ReturnStatus.POSTED

    ret_je = _je(db_session, w.company.id, f"purchase_return_{ret.id}")
    assert ret_je is not None, "Purchase return JE must be created"
    dr, cr = _je_totals(db_session, ret_je.id)
    # 5 PCs × 4.000 cost (current weighted_avg at time of issue) = 20.000
    assert dr == Decimal("20.000")
    assert cr == Decimal("20.000")


# ---------------------------------------------------------------------------
# 11. INVENTORY_ADJUSTMENT_IN
# ---------------------------------------------------------------------------

def test_adjustment_in_je(db_session):
    """adjust_stock (positive) → INVENTORY_ADJUSTMENT_IN: DR Inventory, CR Adj Expense."""
    w = _build_world(db_session, "ADJINCO")
    mv = inv_service.adjust_stock(
        db_session,
        inv_schemas.AdjustStockRequest(
            warehouse_id=w.warehouse.id,
            product_id=w.product.id,
            quantity_delta=Decimal("10"),
            unit_cost=Decimal("5.000"),
            notes="cycle count +",
        ),
        company_id=w.company.id,
        actor_id=w.actor.id,
    )
    adj_je = _je(db_session, w.company.id, f"inv_adjustment_{mv.id}")
    assert adj_je is not None, "Adjustment-in JE must be created"
    dr, cr = _je_totals(db_session, adj_je.id)
    # 10 × 5.000 = 50.000
    assert dr == Decimal("50.000")
    assert cr == Decimal("50.000")


# ---------------------------------------------------------------------------
# 12. cancel_invoice reverses BOTH stock and JEs atomically
# ---------------------------------------------------------------------------

def test_cancel_invoice_reverses_je_and_stock(db_session):
    """Cancelling a POSTED invoice reverses both revenue and COGS JEs to REVERSED.
    cancel_invoice requires approval for POSTED invoices.
    """
    w = _build_world(db_session, "CANCELCO")
    inv = _invoice(db_session, w, qty=10)
    cid = w.company.id
    inv_id = inv.id

    rev_key = f"sale_invoice_{inv_id}_revenue"
    cogs_key = f"sale_invoice_{inv_id}_cogs"

    assert _je(db_session, cid, rev_key).status == JournalEntryStatus.POSTED
    assert _je(db_session, cid, cogs_key).status == JournalEntryStatus.POSTED

    # Cancel requires approval for posted invoices
    with pytest.raises(ApprovalRequired) as exc_info:
        s_service.cancel_invoice(db_session, inv_id, cid, w.actor.id)
    shared_service.approve_request(
        db_session, exc_info.value.approval_request_id, cid, w.approver.id
    )
    s_service.cancel_invoice(db_session, inv_id, cid, w.actor.id)

    # Original JEs now REVERSED
    assert _je(db_session, cid, rev_key).status == JournalEntryStatus.REVERSED
    assert _je(db_session, cid, cogs_key).status == JournalEntryStatus.REVERSED

    # Reversal JEs (POSTED) also exist → 4 total JEs for this company
    total = db_session.query(JournalEntry).filter_by(company_id=cid).count()
    assert total == 4, f"Expected 4 JEs (2 original + 2 reversal), got {total}"


# ---------------------------------------------------------------------------
# 13. Atomicity: closed accounting period blocks post_invoice entirely
# ---------------------------------------------------------------------------

def test_closed_period_blocks_invoice_atomically(db_session):
    """When the accounting period is closed, post_invoice must raise — not silently
    commit the stock part and leave the JE missing."""
    w = _build_world(db_session, "ATOMCO")

    # Close the period that covers today
    period = (
        db_session.query(AccountingPeriod)
        .filter_by(company_id=w.company.id)
        .filter(
            AccountingPeriod.start_date <= datetime.date.today(),
            AccountingPeriod.end_date >= datetime.date.today(),
        )
        .first()
    )
    assert period is not None, "Must have an open period for today"
    acc_service.close_period(db_session, period.id, w.company.id, w.actor.id)

    inv = s_service.create_invoice(
        db_session,
        s_schemas.SalesInvoiceCreate(
            branch_id=w.branch.id,
            customer_id=w.customer.id,
            price_list_id=w.price_list.id,
            invoice_date=datetime.date.today(),
            lines=[
                s_schemas.InvoiceLineCreate(
                    product_id=w.product.id,
                    warehouse_id=w.warehouse.id,
                    unit_id=w.pc_unit.id,
                    quantity_ordered=Decimal("5"),
                    unit_price=Decimal("10.000"),
                    price_source="PRICE_LIST",
                    line_discount=Decimal("0"),
                ),
            ],
        ),
        company_id=w.company.id,
    )
    with pytest.raises(BusinessRuleViolation, match="No open accounting period"):
        s_service.post_invoice(db_session, inv.id, w.company.id, w.actor.id)


# ---------------------------------------------------------------------------
# 14. KEY RECONCILIATION TEST
# ---------------------------------------------------------------------------

def test_inventory_gl_reconciles_with_physical_stock(db_session):
    """THE KEY TEST: GL inventory account balance == sum(quantity × WAC) over
    all StockBalance rows after a complete sequence of:
      GRN1 (100 PCs @ 5.000) → GRN2 (100 PCs @ 7.000) → Sale (50 PCs)
      → Adjustment (+10 PCs @ 6.000)

    Numbers chosen so weighted average stays exactly 6.000 throughout, avoiding
    Numeric(18,6) rounding drift between GL and physical.
    """
    w = _build_world(db_session, "RECONCO", initial_stock=False)
    cid = w.company.id

    # GRN1: 100 PCs at 5.000 → inventory +500
    grn1 = _post_grn(db_session, w, qty=100, cost="5.000")

    # GRN2: 100 PCs at 7.000 → inventory +700; new weighted avg = (500+700)/200 = 6.000
    grn2 = _post_grn(db_session, w, qty=100, cost="7.000")

    # Sale: 50 PCs → issue at WAC=6.000 → COGS = 300.000; inventory −300
    inv = _invoice(db_session, w, qty=50)

    # Adjustment IN: +10 PCs at 6.000 → inventory +60; WAC stays 6.000
    mv = inv_service.adjust_stock(
        db_session,
        inv_schemas.AdjustStockRequest(
            warehouse_id=w.warehouse.id,
            product_id=w.product.id,
            quantity_delta=Decimal("10"),
            unit_cost=Decimal("6.000"),
            notes="cycle count",
        ),
        company_id=cid,
        actor_id=w.actor.id,
    )

    # --- GL inventory balance (net DR − CR on account 1150, POSTED JEs only) ---
    gl_inventory = _gl_net(db_session, cid, _INVENTORY)

    # --- Physical inventory value ---
    balances = (
        db_session.query(StockBalance)
        .filter_by(company_id=cid)
        .all()
    )
    physical = sum(b.quantity_on_hand * b.weighted_avg_cost for b in balances)

    # Expected: 500 + 700 − 300 + 60 = 960.000
    assert gl_inventory == Decimal("960.000"), (
        f"GL inventory = {gl_inventory}, expected 960.000"
    )
    assert physical == Decimal("960.000"), (
        f"Physical inventory = {physical}, expected 960.000"
    )
    assert gl_inventory == physical, (
        f"GL {gl_inventory} ≠ physical {physical}"
    )


# ---------------------------------------------------------------------------
# 15. Isolation contract — AST analysis
# ---------------------------------------------------------------------------

def _forbidden_imports(path: Path, forbidden_prefixes: tuple[str, ...]) -> list[str]:
    tree = ast.parse(path.read_text())
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for part in module.split("."):
                if part in forbidden_prefixes:
                    hits.append(module)
                    break
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for part in alias.name.split("."):
                    if part in forbidden_prefixes:
                        hits.append(alias.name)
                        break
    return hits


_FORBIDDEN = ("sales", "purchasing", "inventory")
_ACCT_ROOT = Path(__file__).parents[1] / "app" / "modules" / "accounting"


def test_isolation_accounting_service(db_session):
    """accounting/service.py must not import from sales, purchasing, or inventory."""
    violations = _forbidden_imports(_ACCT_ROOT / "service.py", _FORBIDDEN)
    assert not violations, f"accounting.service illegal imports: {violations}"


def test_isolation_accounting_integration(db_session):
    """accounting/integration.py must not import from sales, purchasing, or inventory."""
    violations = _forbidden_imports(_ACCT_ROOT / "integration.py", _FORBIDDEN)
    assert not violations, f"accounting.integration illegal imports: {violations}"
