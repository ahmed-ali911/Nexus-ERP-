from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.auth.models import User

from . import models, schemas, service

router = APIRouter(prefix="/sales", tags=["sales"])


# --- Settings ---------------------------------------------------------------


@router.get("/settings", response_model=schemas.SalesSettingsResponse)
def get_settings(
    current_user: User = Depends(require_permission("sales.settings.read")),
    db: Session = Depends(get_db),
):
    return service.get_or_create_settings(db, company_id=current_user.company_id)


@router.patch("/settings", response_model=schemas.SalesSettingsResponse)
def update_settings(
    payload: schemas.SalesSettingsUpdate,
    current_user: User = Depends(require_permission("sales.settings.update")),
    db: Session = Depends(get_db),
):
    return service.update_settings(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


# --- Price Lists ------------------------------------------------------------


@router.post("/price-lists", response_model=schemas.PriceListResponse, status_code=201)
def create_price_list(
    payload: schemas.PriceListCreate,
    current_user: User = Depends(require_permission("sales.price_list.create")),
    db: Session = Depends(get_db),
):
    return service.create_price_list(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.get("/price-lists", response_model=list[schemas.PriceListResponse])
def list_price_lists(
    include_deleted: bool = False,
    current_user: User = Depends(require_permission("sales.price_list.read")),
    db: Session = Depends(get_db),
):
    return service.list_price_lists(
        db, company_id=current_user.company_id, include_deleted=include_deleted
    )


@router.get("/price-lists/{price_list_id}", response_model=schemas.PriceListResponse)
def get_price_list(
    price_list_id: int,
    current_user: User = Depends(require_permission("sales.price_list.read")),
    db: Session = Depends(get_db),
):
    return service.get_price_list(db, price_list_id, company_id=current_user.company_id)


@router.patch("/price-lists/{price_list_id}", response_model=schemas.PriceListResponse)
def update_price_list(
    price_list_id: int,
    payload: schemas.PriceListUpdate,
    current_user: User = Depends(require_permission("sales.price_list.update")),
    db: Session = Depends(get_db),
):
    return service.update_price_list(
        db,
        price_list_id,
        payload,
        company_id=current_user.company_id,
        actor_id=current_user.id,
    )


# --- Price List Items -------------------------------------------------------


@router.post(
    "/price-lists/{price_list_id}/items",
    response_model=schemas.PriceListItemResponse,
    status_code=201,
)
def add_price_list_item(
    price_list_id: int,
    payload: schemas.PriceListItemCreate,
    current_user: User = Depends(require_permission("sales.price_list.update")),
    db: Session = Depends(get_db),
):
    return service.add_price_list_item(
        db,
        price_list_id,
        payload,
        company_id=current_user.company_id,
        actor_id=current_user.id,
    )


@router.get(
    "/price-lists/{price_list_id}/items",
    response_model=list[schemas.PriceListItemResponse],
)
def list_price_list_items(
    price_list_id: int,
    current_user: User = Depends(require_permission("sales.price_list.read")),
    db: Session = Depends(get_db),
):
    return service.list_price_list_items(
        db, price_list_id, company_id=current_user.company_id
    )


@router.patch(
    "/price-lists/items/{item_id}", response_model=schemas.PriceListItemResponse
)
def update_price_list_item(
    item_id: int,
    payload: schemas.PriceListItemUpdate,
    current_user: User = Depends(require_permission("sales.price_list.update")),
    db: Session = Depends(get_db),
):
    return service.update_price_list_item(
        db, item_id, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


# --- Approval Requests ------------------------------------------------------


@router.get("/approvals", response_model=list[schemas.ApprovalRequestResponse])
def list_approvals(
    status: models.ApprovalStatus | None = None,
    reference_type: str | None = None,
    current_user: User = Depends(require_permission("sales.approval.read")),
    db: Session = Depends(get_db),
):
    return service.list_approval_requests(
        db,
        company_id=current_user.company_id,
        status=status,
        reference_type=reference_type,
    )


@router.get("/approvals/{approval_id}", response_model=schemas.ApprovalRequestResponse)
def get_approval(
    approval_id: int,
    current_user: User = Depends(require_permission("sales.approval.read")),
    db: Session = Depends(get_db),
):
    return service.get_approval_request(db, approval_id, company_id=current_user.company_id)


@router.post("/approvals/{approval_id}/approve", response_model=schemas.ApprovalRequestResponse)
def approve_request(
    approval_id: int,
    payload: schemas.ApproveRequestPayload,
    current_user: User = Depends(require_permission("sales.approval.approve")),
    db: Session = Depends(get_db),
):
    return service.approve_request(
        db, approval_id, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.post("/approvals/{approval_id}/reject", response_model=schemas.ApprovalRequestResponse)
def reject_request(
    approval_id: int,
    payload: schemas.RejectRequestPayload,
    current_user: User = Depends(require_permission("sales.approval.approve")),
    db: Session = Depends(get_db),
):
    return service.reject_request(
        db,
        approval_id,
        company_id=current_user.company_id,
        actor_id=current_user.id,
        reason=payload.reason,
    )


# --- Sales Invoices ---------------------------------------------------------


@router.post("/invoices", response_model=schemas.SalesInvoiceResponse, status_code=201)
def create_invoice(
    payload: schemas.SalesInvoiceCreate,
    current_user: User = Depends(require_permission("sales.invoice.create")),
    db: Session = Depends(get_db),
):
    return service.create_invoice(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.get("/invoices", response_model=list[schemas.SalesInvoiceResponse])
def list_invoices(
    customer_id: int | None = None,
    status: models.InvoiceStatus | None = None,
    current_user: User = Depends(require_permission("sales.invoice.read")),
    db: Session = Depends(get_db),
):
    return service.list_invoices(
        db,
        company_id=current_user.company_id,
        customer_id=customer_id,
        status=status,
    )


@router.get("/invoices/{invoice_id}", response_model=schemas.SalesInvoiceDetailResponse)
def get_invoice(
    invoice_id: int,
    current_user: User = Depends(require_permission("sales.invoice.read")),
    db: Session = Depends(get_db),
):
    inv, lines = service.get_invoice_detail(
        db, invoice_id, company_id=current_user.company_id
    )
    result = schemas.SalesInvoiceDetailResponse.model_validate(inv)
    result.lines = [schemas.InvoiceLineResponse.model_validate(ln) for ln in lines]
    return result


@router.post(
    "/invoices/{invoice_id}/post", response_model=schemas.SalesInvoiceResponse
)
def post_invoice(
    invoice_id: int,
    payload: schemas.PostInvoicePayload,
    current_user: User = Depends(require_permission("sales.invoice.post")),
    db: Session = Depends(get_db),
):
    return service.post_invoice(
        db, invoice_id, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.post(
    "/invoices/{invoice_id}/cancel", response_model=schemas.SalesInvoiceResponse
)
def cancel_invoice(
    invoice_id: int,
    payload: schemas.CancelInvoicePayload,
    current_user: User = Depends(require_permission("sales.invoice.cancel")),
    db: Session = Depends(get_db),
):
    return service.cancel_invoice(
        db,
        invoice_id,
        company_id=current_user.company_id,
        actor_id=current_user.id,
        reason=payload.reason,
    )


# --- Credit Notes -----------------------------------------------------------


@router.post("/credit-notes", response_model=schemas.CreditNoteResponse, status_code=201)
def create_credit_note(
    payload: schemas.CreditNoteCreate,
    current_user: User = Depends(require_permission("sales.credit_note.create")),
    db: Session = Depends(get_db),
):
    return service.create_credit_note(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.get("/credit-notes", response_model=list[schemas.CreditNoteResponse])
def list_credit_notes(
    customer_id: int | None = None,
    current_user: User = Depends(require_permission("sales.credit_note.read")),
    db: Session = Depends(get_db),
):
    return service.list_credit_notes(
        db, company_id=current_user.company_id, customer_id=customer_id
    )


@router.get("/credit-notes/{cn_id}", response_model=schemas.CreditNoteDetailResponse)
def get_credit_note(
    cn_id: int,
    current_user: User = Depends(require_permission("sales.credit_note.read")),
    db: Session = Depends(get_db),
):
    cn, lines = service.get_credit_note_detail(
        db, cn_id, company_id=current_user.company_id
    )
    result = schemas.CreditNoteDetailResponse.model_validate(cn)
    result.lines = [schemas.CreditNoteLineResponse.model_validate(ln) for ln in lines]
    return result


@router.post(
    "/credit-notes/{cn_id}/post", response_model=schemas.CreditNoteResponse
)
def post_credit_note(
    cn_id: int,
    current_user: User = Depends(require_permission("sales.credit_note.post")),
    db: Session = Depends(get_db),
):
    return service.post_credit_note(
        db, cn_id, company_id=current_user.company_id, actor_id=current_user.id
    )


# --- Collections ------------------------------------------------------------


@router.post("/collections", response_model=schemas.CollectionResponse, status_code=201)
def create_collection(
    payload: schemas.CollectionCreate,
    current_user: User = Depends(require_permission("sales.collection.create")),
    db: Session = Depends(get_db),
):
    return service.create_collection(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.get("/collections", response_model=list[schemas.CollectionResponse])
def list_collections(
    customer_id: int | None = None,
    current_user: User = Depends(require_permission("sales.collection.read")),
    db: Session = Depends(get_db),
):
    return service.list_collections(
        db, company_id=current_user.company_id, customer_id=customer_id
    )


@router.get("/collections/{collection_id}", response_model=schemas.CollectionDetailResponse)
def get_collection(
    collection_id: int,
    current_user: User = Depends(require_permission("sales.collection.read")),
    db: Session = Depends(get_db),
):
    col, lines = service.get_collection_detail(
        db, collection_id, company_id=current_user.company_id
    )
    result = schemas.CollectionDetailResponse.model_validate(col)
    result.lines = [schemas.CollectionLineResponse.model_validate(ln) for ln in lines]
    return result


@router.post(
    "/collections/{collection_id}/post", response_model=schemas.CollectionResponse
)
def post_collection(
    collection_id: int,
    current_user: User = Depends(require_permission("sales.collection.post")),
    db: Session = Depends(get_db),
):
    return service.post_collection(
        db, collection_id, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.post(
    "/collections/{collection_id}/cancel", response_model=schemas.CollectionResponse
)
def cancel_collection(
    collection_id: int,
    current_user: User = Depends(require_permission("sales.collection.cancel")),
    db: Session = Depends(get_db),
):
    return service.cancel_collection(
        db, collection_id, company_id=current_user.company_id, actor_id=current_user.id
    )
