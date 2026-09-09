"""Real mode: OCR hoa don bang vision LLM tren Groq (chat completions API).

Groq KHONG co API OCR/document-extraction chuyen dung nhu Azure Document
Intelligence - adapter nay gui anh cho 1 model co kha nang doc anh (vision)
kem prompt yeu cau tra ve dung unified JSON schema cua du an, tuan thu
nghiem ngat quy tac "khong tu doan": moi truong khong chac chan phai la
null kem confidence null.

Adapter nay KHONG BAO GIO raise loi ra ngoai - moi loi mang/timeout/API/
JSON hong deu duoc bat va tra ve mot ket qua rong an toan kem review_reason
tuong ung, de tang goi (ocr_service) luon co du lieu hop le de luu.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path

import groq

from app.models.ocr_schema import (
    REASON_OCR_PROVIDER_UNAVAILABLE,
    REASON_OCR_RESPONSE_UNPARSEABLE,
    InvoiceOcrResult,
    empty_result,
)
from app.ocr.base import OcrAdapter

logger = logging.getLogger(__name__)

_MIME_BY_EXT = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

_SCHEMA_EXAMPLE = json.dumps(InvoiceOcrResult().model_dump(), ensure_ascii=False, indent=2)

_SYSTEM_PROMPT = f"""Ban la he thong trich xuat du lieu hoa don (OCR) cho phan mem ke toan.
Nhiem vu: doc anh hoa don duoc cung cap va tra ve DUY NHAT mot doi tuong JSON
dung theo schema duoi day - khong kem giai thich, khong kem markdown, khong
kem bat ky text nao khac ngoai JSON.

QUY TAC BAT BUOC:
1. TUYET DOI KHONG duoc doan hoac suy luan ra mot gia tri ma ban khong thuc
   su doc duoc ro rang tren anh. Neu khong chac chan hoac khong tim thay,
   dat "value": null va "confidence": null cho truong do.
2. Neu "value" khac null thi "confidence" (so thuc 0.0-1.0) BAT BUOC phai
   co, khong duoc de null.
3. "invoice_date" neu doc duoc, tra theo dinh dang ISO YYYY-MM-DD.
3b. "invoice_type_name" la TEN LOAI CHUNG TU, thuong la dong chu in to o
    phia tren cung hoa don (vd "HOA DON GIA TRI GIA TANG", "HOA DON BAN
    HANG"). Day KHONG PHAI la "Mau so" hay "Ky hieu".
3c. "invoice_form_number" la gia tri cua truong "Mau so" in o goc tren ben
    phai hoa don (vd "01GTKT3/001", "01GTKT0/001"). KHAC voi "Ky hieu" (vd
    TU/21P) - neu anh chi co Ky hieu ma khong co dong "Mau so:" rieng, de
    "invoice_form_number" la null, KHONG dung gia tri Ky hieu thay the.
3d. Cac truong ve nguoi mua (buyer_name, buyer_tax_code, buyer_company_name,
    buyer_address, buyer_bank_account, buyer_payment_method) doc tu phan
    "nguoi mua"/"don vi mua hang" cua hoa don: "buyer_name" la ho ten ca
    nhan nguoi mua hang (dong "Ho ten nguoi mua hang"), "buyer_company_name"
    la ten don vi/cong ty cua nguoi mua (dong "Ten don vi", co the khac voi
    buyer_name), "buyer_address" la dia chi don vi mua, "buyer_bank_account"
    la so tai khoan ngan hang cua nguoi mua (dong "So tai khoan"),
    "buyer_payment_method" la hinh thuc thanh toan (vd "TM/CK", "Tien mat",
    "Chuyen khoan"). Neu hoa don khong co dong nao trong so nay, de null.
4. "subtotal", "tax_amount", "total_amount" la so (khong phai chuoi), khong
   kem ky hieu tien te.
5. "line_items" la danh sach dong hang/dich vu, co the de rong [] neu khong
   doc duoc dong nao. Moi phan tu PHAI dung dung 5 ten khoa sau, khong duoc
   doi ten: "description", "quantity", "unit_price", "line_total",
   "confidence".
6. "review_reasons" la danh sach ma ly do (string ngan gon, khong dau) ban
   tu nhan thay hoa don co van de can nguoi kiem tra lai (vd anh mo, chu
   viet tay kho doc). Co the de rong [].
7. Chi tra ve JSON dung cau truc sau, khong them truong nao khac, khong bo
   truong nao. KHONG bao boc JSON trong markdown code fence, KHONG viet
   phan suy nghi/giai thich truoc hoac sau JSON:

{_SCHEMA_EXAMPLE}
"""

_USER_PROMPT = "Day la anh hoa don can trich xuat du lieu. Hay tra ve JSON theo dung schema va quy tac da neu."


class GroqOcrAdapter(OcrAdapter):
    """Real mode: goi Groq vision chat completions de trich xuat hoa don."""

    provider_name = "groq"

    def __init__(self, api_key: str, model: str, timeout_seconds: float, max_retries: int):
        self._client = groq.Groq(api_key=api_key, timeout=timeout_seconds, max_retries=max_retries)
        self._model = model

    def extract(self, image_path: Path) -> dict:
        try:
            data_url = _encode_image_data_url(image_path)
        except OSError:
            logger.exception("Khong doc duoc file anh de gui OCR: %s", image_path)
            return empty_result([REASON_OCR_PROVIDER_UNAVAILABLE])

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                max_tokens=4096,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _USER_PROMPT},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
            )
        except groq.APIError:
            logger.exception("Loi goi Groq API (mang/timeout/API) khi OCR anh %s", image_path)
            return empty_result([REASON_OCR_PROVIDER_UNAVAILABLE])
        except Exception:
            logger.exception("Loi khong luong truoc khi goi Groq API")
            return empty_result([REASON_OCR_PROVIDER_UNAVAILABLE])

        try:
            content = response.choices[0].message.content
            raw = json.loads(_extract_json_text(content))
        except (json.JSONDecodeError, AttributeError, IndexError, TypeError):
            logger.exception("Groq tra ve noi dung khong phai JSON hop le")
            return empty_result([REASON_OCR_RESPONSE_UNPARSEABLE])

        return raw


_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _extract_json_text(content: str) -> str:
    """Boc tach phan JSON tu noi dung model tra ve.

    Mot so model "reasoning" tren Groq (vd cac model qwen/deepseek) van xen
    khoi <think>...</think> va bao JSON trong markdown code fence du prompt
    da yeu cau khong lam vay, va API cung khong ho tro ep JSON mode cho cac
    model nay (tra loi 400 json_validate_failed). Vi vay tu boc tach thay vi
    dua vao response_format cua API.
    """
    if not content:
        raise json.JSONDecodeError("empty content", content or "", 0)

    text = _THINK_BLOCK_RE.sub("", content).strip()

    fence_match = _CODE_FENCE_RE.search(text)
    if fence_match:
        return fence_match.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return text


def _encode_image_data_url(image_path: Path) -> str:
    mime = _MIME_BY_EXT.get(image_path.suffix.lower(), "image/jpeg")
    raw_bytes = image_path.read_bytes()
    b64 = base64.b64encode(raw_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"
