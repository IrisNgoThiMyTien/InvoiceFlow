import json
import sqlite3
from datetime import datetime, timezone

from app.db import get_connection
from app.models.ocr_schema import HEADER_FIELDS
from app.models.schema import InvoiceStatus

# Cac cot header duoc cap nhat qua UPDATE dong (khac 'currency', vi currency
# giu gia tri cu neu OCR khong tra ve gi - xem update_ocr_result).
_UPDATABLE_HEADER_FIELDS = [name for name in HEADER_FIELDS if name != "currency"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_pending_invoice(stored_filename: str, original_filename: str) -> int:
    """Tao 1 ban ghi hoa don moi voi trang thai 'pending_review' (hien thi 'Mới').

    Chua co du lieu OCR nao o buoc nay - moi field nghiep vu deu de NULL.
    """
    now = _now_iso()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO invoices (
                original_filename, stored_filename, uploaded_at, status, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (original_filename, stored_filename, now, InvoiceStatus.PENDING_REVIEW.value, now),
        )
        return cur.lastrowid


def get_invoice(invoice_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        cur = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
        return cur.fetchone()


def list_invoices() -> list[sqlite3.Row]:
    with get_connection() as conn:
        cur = conn.execute("SELECT * FROM invoices ORDER BY uploaded_at DESC")
        return cur.fetchall()


def list_line_items(invoice_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT * FROM invoice_line_items WHERE invoice_id = ? ORDER BY line_number",
            (invoice_id,),
        )
        return cur.fetchall()


def _replace_line_items(conn, invoice_id: int, line_items: list[dict]) -> None:
    conn.execute("DELETE FROM invoice_line_items WHERE invoice_id = ?", (invoice_id,))
    for idx, item in enumerate(line_items, start=1):
        conn.execute(
            """
            INSERT INTO invoice_line_items (
                invoice_id, line_number, description, quantity, unit_price, line_total
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                invoice_id,
                idx,
                item.get("description"),
                item.get("quantity"),
                item.get("unit_price"),
                item.get("line_total"),
            ),
        )


def update_ocr_result(invoice_id: int, ocr_provider: str, ocr_raw_json: str, normalized: dict) -> None:
    """Ghi ket qua OCR (da kiem tra/chuan hoa) vao 1 hoa don co san.

    Khong doi 'status' o buoc nay - hoa don van giu 'pending_review' ('Mới')
    cho toi khi nguoi dung sua/xac nhan o buoc sau; can_ra_soat duoc suy ra
    tu review_reasons luc hien thi, khong can them cot rieng.
    """

    def field_value(name: str):
        return normalized.get(name, {}).get("value")

    now = _now_iso()
    set_clause = ", ".join(f"{name} = ?" for name in _UPDATABLE_HEADER_FIELDS)
    values = [field_value(name) for name in _UPDATABLE_HEADER_FIELDS]
    values += [
        field_value("currency"),
        json.dumps(normalized.get("review_reasons", []), ensure_ascii=False),
        ocr_raw_json,
        ocr_provider,
        now,
        invoice_id,
    ]

    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE invoices SET
                {set_clause},
                currency = COALESCE(?, currency),
                review_reasons = ?,
                ocr_raw_json = ?,
                ocr_provider = ?,
                updated_at = ?
            WHERE id = ?
            """,
            values,
        )
        _replace_line_items(conn, invoice_id, normalized.get("line_items", []))


def save_reviewed_invoice(invoice_id: int, header: dict, line_items: list[dict]) -> None:
    """Luu du lieu nguoi dung da ra soat/nhap tay va danh dau 'confirmed'.

    review_reasons duoc xoa vi nguoi dung da xem va xac nhan du lieu - cac
    canh bao thieu truong/tu OCR khong con y nghia nua. Canh bao nghiep vu
    khac (tong tien lech, trung hoa don...) se do 1 buoc rieng sau nay tao
    ra, khong lien quan toi buoc luu nay.
    """
    now = _now_iso()
    set_clause = ", ".join(f"{name} = ?" for name in _UPDATABLE_HEADER_FIELDS)
    values = [header.get(name) for name in _UPDATABLE_HEADER_FIELDS]
    values += [
        header.get("currency") or "VND",
        InvoiceStatus.CONFIRMED.value,
        now,
        now,
        invoice_id,
    ]

    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE invoices SET
                {set_clause},
                currency = ?,
                review_reasons = '[]',
                status = ?,
                confirmed_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            values,
        )
        _replace_line_items(conn, invoice_id, line_items)
