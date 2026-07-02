from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import BusinessRuleViolation, NotFoundError
from app.modules.master_data import schemas, service
from app.modules.master_data.models import (
    CustomerType,
    PaymentTerms,
    ProductType,
    UnitConversion,
    UnitType,
)
from app.modules.organization import schemas as org_schemas
from app.modules.organization import service as org_service


def _make_company(db, code="MDCO"):
    return org_service.create_company(
        db,
        org_schemas.CompanyCreate(
            code=code,
            name_en=f"{code} Co",
            name_ar=f"شركة {code}",
            commercial_registration_no=f"CR-{code}",
        ),
    )


def _make_unit(db, company_id, code, unit_type, symbol=None):
    return service.create_unit(
        db,
        schemas.UnitOfMeasureCreate(
            code=code, name_en=code, name_ar=code, symbol=symbol or code[:3], unit_type=unit_type
        ),
        company_id=company_id,
    )


def _make_category(db, company_id, code="CAT1", parent_id=None):
    return service.create_category(
        db,
        schemas.CategoryCreate(code=code, name_en=code, name_ar=code, parent_id=parent_id),
        company_id=company_id,
    )


def _make_product(
    db,
    company_id,
    category_id,
    base_unit_id,
    code="PROD1",
    product_type=ProductType.FINISHED_GOOD,
    **kwargs,
):
    return service.create_product(
        db,
        schemas.ProductCreate(
            code=code,
            name_en=code,
            name_ar=code,
            category_id=category_id,
            product_type=product_type,
            base_unit_id=base_unit_id,
            **kwargs,
        ),
        company_id=company_id,
    )


# --- Weight conversions (exactness) -------------------------------------


def test_weight_conversion_exact_no_rounding_drift(db_session):
    company = _make_company(db_session, code="WCO")
    gram = _make_unit(db_session, company.id, "G", UnitType.WEIGHT, "g")
    kg = _make_unit(db_session, company.id, "KG", UnitType.WEIGHT, "kg")
    ton = _make_unit(db_session, company.id, "TON", UnitType.WEIGHT, "t")

    service.create_conversion(
        db_session,
        schemas.UnitConversionCreate(
            from_unit_id=kg.id, to_unit_id=gram.id, factor=Decimal("1000")
        ),
        company_id=company.id,
    )
    service.create_conversion(
        db_session,
        schemas.UnitConversionCreate(
            from_unit_id=ton.id, to_unit_id=gram.id, factor=Decimal("1000000")
        ),
        company_id=company.id,
    )
    service.create_conversion(
        db_session,
        schemas.UnitConversionCreate(from_unit_id=ton.id, to_unit_id=kg.id, factor=Decimal("1000")),
        company_id=company.id,
    )

    factor_to_grams = service.get_conversion_factor(db_session, company.id, ton.id, gram.id)
    factor_to_kg = service.get_conversion_factor(db_session, company.id, ton.id, kg.id)

    assert Decimal("1") * factor_to_grams == Decimal("1000000")
    assert Decimal("1") * factor_to_kg == Decimal("1000")

    # reverse direction derived correctly too (no stored row for gram->ton)
    factor_gram_to_ton = service.get_conversion_factor(db_session, company.id, gram.id, ton.id)
    assert factor_gram_to_ton == Decimal("1") / Decimal("1000000")


# --- Count conversions (product-specific) -------------------------------


def test_count_conversion_exact_and_product_specific(db_session):
    company = _make_company(db_session, code="CCO")
    piece = _make_unit(db_session, company.id, "PC", UnitType.COUNT, "pc")
    carton = _make_unit(db_session, company.id, "CTN", UnitType.COUNT, "ctn")
    category = _make_category(db_session, company.id)
    product_a = _make_product(db_session, company.id, category.id, piece.id, code="PRODA")
    product_b = _make_product(db_session, company.id, category.id, piece.id, code="PRODB")

    service.create_conversion(
        db_session,
        schemas.UnitConversionCreate(
            product_id=product_a.id,
            from_unit_id=carton.id,
            to_unit_id=piece.id,
            factor=Decimal("12"),
        ),
        company_id=company.id,
    )
    service.create_conversion(
        db_session,
        schemas.UnitConversionCreate(
            product_id=product_b.id,
            from_unit_id=carton.id,
            to_unit_id=piece.id,
            factor=Decimal("24"),
        ),
        company_id=company.id,
    )

    factor_a = service.get_conversion_factor(
        db_session, company.id, carton.id, piece.id, product_id=product_a.id
    )
    factor_b = service.get_conversion_factor(
        db_session, company.id, carton.id, piece.id, product_id=product_b.id
    )

    assert factor_a == Decimal("12")
    assert factor_b == Decimal("24")


# --- Cross-type rejection ------------------------------------------------


def test_cross_type_conversion_rejected(db_session):
    company = _make_company(db_session, code="XTCO")
    gram = _make_unit(db_session, company.id, "G", UnitType.WEIGHT, "g")
    piece = _make_unit(db_session, company.id, "PC", UnitType.COUNT, "pc")

    with pytest.raises(BusinessRuleViolation):
        service.create_conversion(
            db_session,
            schemas.UnitConversionCreate(
                from_unit_id=gram.id, to_unit_id=piece.id, factor=Decimal("1")
            ),
            company_id=company.id,
        )


def test_product_unit_assignment_rejected_cross_type(db_session):
    company = _make_company(db_session, code="PUCO")
    gram = _make_unit(db_session, company.id, "G", UnitType.WEIGHT, "g")
    piece = _make_unit(db_session, company.id, "PC", UnitType.COUNT, "pc")
    category = _make_category(db_session, company.id)

    with pytest.raises(BusinessRuleViolation):
        _make_product(
            db_session, company.id, category.id, gram.id, code="BADPROD", sales_unit_id=piece.id
        )


# --- Category cycle prevention -------------------------------------------


def test_category_cycle_prevention(db_session):
    company = _make_company(db_session, code="CYCCO")
    parent = _make_category(db_session, company.id, code="PARENT")
    child = _make_category(db_session, company.id, code="CHILD")
    service.update_category(db_session, child.id, schemas.CategoryUpdate(parent_id=parent.id))

    with pytest.raises(BusinessRuleViolation):
        service.update_category(db_session, parent.id, schemas.CategoryUpdate(parent_id=child.id))


def test_category_cannot_be_own_parent(db_session):
    company = _make_company(db_session, code="SELFPARCO")
    category = _make_category(db_session, company.id, code="SELFPAR")

    with pytest.raises(BusinessRuleViolation):
        service.update_category(
            db_session, category.id, schemas.CategoryUpdate(parent_id=category.id)
        )


# --- Conversion factor positivity ----------------------------------------


def test_conversion_factor_rejects_zero_via_pydantic():
    with pytest.raises(PydanticValidationError):
        schemas.UnitConversionCreate(from_unit_id=1, to_unit_id=2, factor=Decimal("0"))


def test_conversion_factor_rejects_negative_at_db_level(db_session):
    company = _make_company(db_session, code="NEGCO")
    gram = _make_unit(db_session, company.id, "G", UnitType.WEIGHT, "g")
    kg = _make_unit(db_session, company.id, "KG", UnitType.WEIGHT, "kg")
    conversion = UnitConversion(
        company_id=company.id, from_unit_id=kg.id, to_unit_id=gram.id, factor=Decimal("-5")
    )
    db_session.add(conversion)
    with pytest.raises(IntegrityError):
        db_session.flush()


# --- Company scoping -------------------------------------------------------


def test_company_scoping_cannot_reference_unit_from_another_company(db_session):
    company_a = _make_company(db_session, code="SCA")
    company_b = _make_company(db_session, code="SCB")
    unit_b = _make_unit(db_session, company_b.id, "G", UnitType.WEIGHT, "g")
    category_a = _make_category(db_session, company_a.id)

    with pytest.raises(NotFoundError):
        _make_product(db_session, company_a.id, category_a.id, unit_b.id, code="CROSSPROD")


def test_company_scoping_cannot_reference_category_from_another_company(db_session):
    company_a = _make_company(db_session, code="SCA2")
    company_b = _make_company(db_session, code="SCB2")
    category_b = _make_category(db_session, company_b.id, code="CATB")
    unit_a = _make_unit(db_session, company_a.id, "G", UnitType.WEIGHT, "g")

    with pytest.raises(NotFoundError):
        _make_product(db_session, company_a.id, category_b.id, unit_a.id, code="CROSSPROD2")


# --- Product flags ---------------------------------------------------------


def test_sellable_purchasable_stockable_flags_stored_and_queryable(db_session):
    company = _make_company(db_session, code="FLAGCO")
    gram = _make_unit(db_session, company.id, "G", UnitType.WEIGHT, "g")
    category = _make_category(db_session, company.id)
    product = _make_product(
        db_session,
        company.id,
        category.id,
        gram.id,
        code="SERVICEISH",
        is_sellable=False,
        is_purchasable=True,
        is_stockable=False,
    )
    fetched = service.get_product(db_session, product.id)
    assert fetched.is_sellable is False
    assert fetched.is_purchasable is True
    assert fetched.is_stockable is False


def test_purchase_and_sales_unit_resolve_to_base_when_unset(db_session):
    company = _make_company(db_session, code="EFFCO")
    gram = _make_unit(db_session, company.id, "G", UnitType.WEIGHT, "g")
    category = _make_category(db_session, company.id)
    product = _make_product(db_session, company.id, category.id, gram.id, code="EFFPROD")
    assert product.effective_purchase_unit_id == gram.id
    assert product.effective_sales_unit_id == gram.id


# --- Barcode uniqueness ----------------------------------------------------


def test_barcode_unique_within_company(db_session):
    company = _make_company(db_session, code="BARCO")
    gram = _make_unit(db_session, company.id, "G", UnitType.WEIGHT, "g")
    category = _make_category(db_session, company.id)
    _make_product(db_session, company.id, category.id, gram.id, code="P1", barcode="1234567890")
    with pytest.raises(IntegrityError):
        _make_product(db_session, company.id, category.id, gram.id, code="P2", barcode="1234567890")


def test_multiple_products_without_barcode_allowed(db_session):
    company = _make_company(db_session, code="NOBARCO")
    gram = _make_unit(db_session, company.id, "G", UnitType.WEIGHT, "g")
    category = _make_category(db_session, company.id)
    _make_product(db_session, company.id, category.id, gram.id, code="P1")
    _make_product(db_session, company.id, category.id, gram.id, code="P2")


# --- Customer credit_limit constraint -------------------------------------


def test_customer_credit_limit_requires_credit_terms_via_pydantic():
    with pytest.raises(PydanticValidationError):
        schemas.CustomerCreate(
            code="C1",
            name_en="C1",
            name_ar="C1",
            customer_type=CustomerType.SHOP,
            payment_terms=PaymentTerms.CASH,
            credit_limit=Decimal("1000"),
        )


def test_customer_credit_customer_with_limit_allowed(db_session):
    company = _make_company(db_session, code="CREDITCO")
    customer = service.create_customer(
        db_session,
        schemas.CustomerCreate(
            code="C1",
            name_en="C1",
            name_ar="C1",
            customer_type=CustomerType.COMPANY,
            payment_terms=PaymentTerms.CREDIT,
            credit_limit=Decimal("5000.000"),
        ),
        company_id=company.id,
    )
    assert customer.credit_limit == Decimal("5000.000")
