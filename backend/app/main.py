from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.modules.organization.router import router as organization_router

app = FastAPI(title=settings.APP_NAME)


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    return JSONResponse(
        status_code=409, content={"detail": "Conflict: duplicate value or constraint violation"}
    )


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(organization_router, prefix="/api/v1")
