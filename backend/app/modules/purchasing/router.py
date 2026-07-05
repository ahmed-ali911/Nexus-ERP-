from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_actor_id, get_company_id

from . import schemas, service
from .models import BillStatus, GRNStatus, POStatus

router = APIRouter(tags=["purchasing"])


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@router.get("/purchasing/settings", response_model=schemas.PurchaseSettingsResponse)
def get_settings(
    company_id: int = Depends(get_company_id),
    db: Session = Depends(get_db),
):
    return service.get_or_create_settings(db, company_id)


@router.patch("/purchasing/settings", response_model=schemas.PurchaseSettingsResponse)
def patch_settings(
    payload: schemas.PurchaseSettingsUpdate,
    company_id: int = Depends(get_company_id),
    actor_id: int | None = Depends(get_actor_id),
    db: Session = Depends(get_db),
):
    return service.update_settings(db, payload, company_id, actor_id)


# ---------------------------------------------------------------------------
# PurchaseOrder
# ---------------------------------------------------------------------------


@router.post(
    "/purchasing/purchase-orders",
    response_model=schemas.PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_po(
    payload: schemas.PurchaseOrderCreate,
    company_id: int = Depends(get_company_id),
    actor_id: int | None = Depends(get_actor_id),
    db: Session = Depends(get_db),
):
    return service.create_po(db, payload, company_id, actor_id)


@router.get(
    "/purchasing/purchase-orders",
    response_model=list[schemas.PurchaseOrderResponse],
)
def list_pos(
    supplier_id: int | None = None,
    po_status: POStatus | None = None,
    company_id: int = Depends(get_company_id),
    db: Session = Depends(get_db),
):
    return service.list_pos(db, company_id, supplier_id=supplier_id, status=po_status)


@router.get(
    "/purchasing/purchase-orders/{po_id}",
    response_model=schemas.PurchaseOrderDetailResponse,
)
def get_po(
    po_id: int,
    company_id: int = Depends(get_company_id),
    db: Session = Depends(get_db),
):
    po, lines = service.get_po_detail(db, po_id, company_id)
    return schemas.PurchaseOrderDetailResponse(**po.__dict__, lines=lines)


@router.post(
    "/purchasing/purchase-orders/{po_id}/approve",
    response_model=schemas.PurchaseOrderResponse,
)
def approve_po(
    po_id: int,
    company_id: int = Depends(get_company_id),
    actor_id: int | None = Depends(get_actor_id),
    db: Session = Depends(get_db),
):
    return service.approve_po(db, po_id, company_id, actor_id)


@router.post(
    "/purchasing/purchase-orders/{po_id}/cancel",
    response_model=schemas.PurchaseOrderResponse,
)
def cancel_po(
    po_id: int,
    payload: schemas.CancelPOPayload,
    company_id: int = Depends(get_company_id),
    actor_id: int | None = Depends(get_actor_id),
    db: Session = Depends(get_db),
):
    return service.cancel_po(db, po_id, company_id, actor_id)


# ---------------------------------------------------------------------------
# GoodsReceipt
# ---------------------------------------------------------------------------


@router.post(
    "/purchasing/grns",
    response_model=schemas.GoodsReceiptResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_grn(
    payload: schemas.GoodsReceiptCreate,
    company_id: int = Depends(get_company_id),
    actor_id: int | None = Depends(get_actor_id),
    db: Session = Depends(get_db),
):
    return service.create_grn(db, payload, company_id, actor_id)


@router.get(
    "/purchasing/grns",
    response_model=list[schemas.GoodsReceiptResponse],
)
def list_grns(
    supplier_id: int | None = None,
    grn_status: GRNStatus | None = None,
    company_id: int = Depends(get_company_id),
    db: Session = Depends(get_db),
):
    return service.list_grns(db, company_id, supplier_id=supplier_id, status=grn_status)


@router.get(
    "/purchasing/grns/{grn_id}",
    response_model=schemas.GoodsReceiptDetailResponse,
)
def get_grn(
    grn_id: int,
    company_id: int = Depends(get_company_id),
    db: Session = Depends(get_db),
):
    grn, lines = service.get_grn_detail(db, grn_id, company_id)
    return schemas.GoodsReceiptDetailResponse(**grn.__dict__, lines=lines)


@router.post(
    "/purchasing/grns/{grn_id}/post",
    response_model=schemas.GoodsReceiptResponse,
)
def post_grn(
    grn_id: int,
    company_id: int = Depends(get_company_id),
    actor_id: int | None = Depends(get_actor_id),
    db: Session = Depends(get_db),
):
    return service.post_grn(db, grn_id, company_id, actor_id)


@router.post(
    "/purchasing/grns/{grn_id}/cancel",
    response_model=schemas.GoodsReceiptResponse,
)
def cancel_grn(
    grn_id: int,
    payload: schemas.CancelGRNPayload,
    company_id: int = Depends(get_company_id),
    actor_id: int | None = Depends(get_actor_id),
    db: Session = Depends(get_db),
):
    return service.cancel_grn(db, grn_id, company_id, actor_id, reason=payload.reason)


# ---------------------------------------------------------------------------
# SupplierInvoice
# ---------------------------------------------------------------------------


@router.post(
    "/purchasing/bills",
    response_model=schemas.SupplierInvoiceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_bill(
    payload: schemas.SupplierInvoiceCreate,
    company_id: int = Depends(get_company_id),
    actor_id: int | None = Depends(get_actor_id),
    db: Session = Depends(get_db),
):
    return service.create_supplier_invoice(db, payload, company_id, actor_id)


@router.get(
    "/purchasing/bills",
    response_model=list[schemas.SupplierInvoiceResponse],
)
def list_bills(
    supplier_id: int | None = None,
    bill_status: BillStatus | None = None,
    company_id: int = Depends(get_company_id),
    db: Session = Depends(get_db),
):
    return service.list_supplier_invoices(db, company_id, supplier_id=supplier_id, status=bill_status)


@router.get(
    "/purchasing/bills/{bill_id}",
    response_model=schemas.SupplierInvoiceDetailResponse,
)
def get_bill(
    bill_id: int,
    company_id: int = Depends(get_company_id),
    db: Session = Depends(get_db),
):
    bill, lines = service.get_supplier_invoice_detail(db, bill_id, company_id)
    return schemas.SupplierInvoiceDetailResponse(**bill.__dict__, lines=lines)


@router.post(
    "/purchasing/bills/{bill_id}/post",
    response_model=schemas.SupplierInvoiceResponse,
)
def post_bill(
    bill_id: int,
    company_id: int = Depends(get_company_id),
    actor_id: int | None = Depends(get_actor_id),
    db: Session = Depends(get_db),
):
    return service.post_supplier_invoice(db, bill_id, company_id, actor_id)


@router.post(
    "/purchasing/bills/{bill_id}/cancel",
    response_model=schemas.SupplierInvoiceResponse,
)
def cancel_bill(
    bill_id: int,
    payload: schemas.CancelBillPayload,
    company_id: int = Depends(get_company_id),
    actor_id: int | None = Depends(get_actor_id),
    db: Session = Depends(get_db),
):
    return service.cancel_supplier_invoice(db, bill_id, company_id, actor_id, reason=payload.reason)


# ---------------------------------------------------------------------------
# PurchaseReturn
# ---------------------------------------------------------------------------


@router.post(
    "/purchasing/returns",
    response_model=schemas.PurchaseReturnResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_return(
    payload: schemas.PurchaseReturnCreate,
    company_id: int = Depends(get_company_id),
    actor_id: int | None = Depends(get_actor_id),
    db: Session = Depends(get_db),
):
    return service.create_purchase_return(db, payload, company_id, actor_id)


@router.get(
    "/purchasing/returns",
    response_model=list[schemas.PurchaseReturnResponse],
)
def list_returns(
    supplier_id: int | None = None,
    company_id: int = Depends(get_company_id),
    db: Session = Depends(get_db),
):
    return service.list_purchase_returns(db, company_id, supplier_id=supplier_id)


@router.get(
    "/purchasing/returns/{return_id}",
    response_model=schemas.PurchaseReturnDetailResponse,
)
def get_return(
    return_id: int,
    company_id: int = Depends(get_company_id),
    db: Session = Depends(get_db),
):
    ret, lines = service.get_purchase_return_detail(db, return_id, company_id)
    return schemas.PurchaseReturnDetailResponse(**ret.__dict__, lines=lines)


@router.post(
    "/purchasing/returns/{return_id}/post",
    response_model=schemas.PurchaseReturnResponse,
)
def post_return(
    return_id: int,
    company_id: int = Depends(get_company_id),
    actor_id: int | None = Depends(get_actor_id),
    db: Session = Depends(get_db),
):
    return service.post_purchase_return(db, return_id, company_id, actor_id)


# ---------------------------------------------------------------------------
# SupplierPayment
# ---------------------------------------------------------------------------


@router.post(
    "/purchasing/payments",
    response_model=schemas.SupplierPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    payload: schemas.SupplierPaymentCreate,
    company_id: int = Depends(get_company_id),
    actor_id: int | None = Depends(get_actor_id),
    db: Session = Depends(get_db),
):
    return service.create_supplier_payment(db, payload, company_id, actor_id)


@router.get(
    "/purchasing/payments",
    response_model=list[schemas.SupplierPaymentResponse],
)
def list_payments(
    supplier_id: int | None = None,
    company_id: int = Depends(get_company_id),
    db: Session = Depends(get_db),
):
    return service.list_supplier_payments(db, company_id, supplier_id=supplier_id)


@router.get(
    "/purchasing/payments/{payment_id}",
    response_model=schemas.SupplierPaymentDetailResponse,
)
def get_payment(
    payment_id: int,
    company_id: int = Depends(get_company_id),
    db: Session = Depends(get_db),
):
    payment, lines = service.get_supplier_payment_detail(db, payment_id, company_id)
    return schemas.SupplierPaymentDetailResponse(**payment.__dict__, lines=lines)


@router.post(
    "/purchasing/payments/{payment_id}/post",
    response_model=schemas.SupplierPaymentResponse,
)
def post_payment(
    payment_id: int,
    company_id: int = Depends(get_company_id),
    actor_id: int | None = Depends(get_actor_id),
    db: Session = Depends(get_db),
):
    return service.post_supplier_payment(db, payment_id, company_id, actor_id)


@router.post(
    "/purchasing/payments/{payment_id}/cancel",
    response_model=schemas.SupplierPaymentResponse,
)
def cancel_payment(
    payment_id: int,
    company_id: int = Depends(get_company_id),
    actor_id: int | None = Depends(get_actor_id),
    db: Session = Depends(get_db),
):
    return service.cancel_supplier_payment(db, payment_id, company_id, actor_id)


# ---------------------------------------------------------------------------
# Approval endpoints (shared framework, purchasing reference types)
# ---------------------------------------------------------------------------


@router.post("/purchasing/approvals/{approval_id}/approve")
def approve_request(
    approval_id: int,
    company_id: int = Depends(get_company_id),
    actor_id: int | None = Depends(get_actor_id),
    db: Session = Depends(get_db),
):
    return service.approve_request(db, approval_id, company_id, actor_id)


@router.post("/purchasing/approvals/{approval_id}/reject")
def reject_request(
    approval_id: int,
    reason: str | None = None,
    company_id: int = Depends(get_company_id),
    actor_id: int | None = Depends(get_actor_id),
    db: Session = Depends(get_db),
):
    return service.reject_request(db, approval_id, company_id, actor_id, reason)
