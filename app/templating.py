"""1 instance Jinja2Templates dung chung cho toan bo app.

Tap trung o day de dang ky 1 global 'asset_version' duy nhat - dung lam
cache-buster cho file static (CSS/JS), tranh tinh trang trinh duyet giu
CSS cu trong cache sau khi da sua file tren server (nguoi dung phai bam
Ctrl+F5 moi thay thay doi, gay nham lan).
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

_STATIC_DIR = Path("app/static")

templates = Jinja2Templates(directory="app/templates")


def _asset_version() -> str:
    """Tra ve 1 gia tri thay doi moi khi bat ky file trong static/ thay doi,
    dung lam query string '?v=...' de ep trinh duyet tai lai CSS/JS moi."""
    try:
        latest = max((f.stat().st_mtime_ns for f in _STATIC_DIR.rglob("*") if f.is_file()), default=0)
    except OSError:
        latest = 0
    return str(latest)


templates.env.globals["asset_version"] = _asset_version
