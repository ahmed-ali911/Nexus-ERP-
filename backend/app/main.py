from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.exceptions import AuthenticationError, BusinessRuleViolation, NotFoundError
from app.modules.auth.router import router as auth_router
from app.modules.master_data.router import router as master_data_router
from app.modules.organization.router import router as organization_router

app = FastAPI(title=settings.APP_NAME)


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(AuthenticationError)
async def authentication_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(BusinessRuleViolation)
async def business_rule_violation_handler(
    request: Request, exc: BusinessRuleViolation
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    return JSONResponse(
        status_code=409, content={"detail": "Conflict: duplicate value or constraint violation"}
    )


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth_router, prefix="/api/v1")
app.include_router(organization_router, prefix="/api/v1")
app.include_router(master_data_router, prefix="/api/v1")
