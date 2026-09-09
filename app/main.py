import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import init_db
from app.routers import invoices, upload
from app.templating import templates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="InvoiceFlow")

app.include_router(upload.router)
app.include_router(invoices.router)

settings.upload_dir_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(settings.upload_dir_path)), name="uploads")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return RedirectResponse(url="/invoices")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse(
        request, "error.html", {"message": exc.detail}, status_code=exc.status_code
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Loi khong mong doi khi xu ly request %s", request.url)
    return templates.TemplateResponse(
        request,
        "error.html",
        {"message": "Có lỗi hệ thống không mong muốn. Vui lòng thử lại sau."},
        status_code=500,
    )
