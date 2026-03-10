"""Resume parsing helper functions.

这里保留纯工具函数，避免路由文件膨胀。
"""

from __future__ import annotations

import json
from io import BytesIO


def extract_image_text(img_bytes: bytes) -> str:
    """OCR text extraction with lazy imports.

    懒加载依赖，避免没有安装相关包时影响非简历接口启动。
    """
    try:
        from PIL import Image
        import pytesseract

        img = Image.open(BytesIO(img_bytes))
        return pytesseract.image_to_string(img, lang="chi_sim").strip()
    except Exception:
        return ""


def extract_all_content(file_bytes: bytes, filename: str) -> str:
    """Extract text content from PDF/Word/image/txt files."""
    text_parts: list[str] = []
    lower_name = filename.lower()

    if lower_name.endswith(".pdf"):
        try:
            import pdfplumber
        except Exception as e:
            raise ValueError(f"缺少 pdfplumber 依赖: {str(e)}")

        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
                for img_info in (page.images or [])[:3]:
                    stream = img_info.get("stream")
                    if stream:
                        ocr_text = extract_image_text(stream.get_data())
                        if ocr_text:
                            text_parts.append(ocr_text)

    elif lower_name.endswith(".docx"):
        try:
            import docx
        except Exception as e:
            raise ValueError(f"缺少 python-docx 依赖: {str(e)}")

        doc = docx.Document(BytesIO(file_bytes))
        text_parts.extend(p.text.strip() for p in doc.paragraphs if p.text.strip())

    elif lower_name.endswith(".doc"):
        raise ValueError("暂不支持 .doc（旧版 Word）格式，请另存为 .docx 后上传")

    elif lower_name.endswith((".png", ".jpg", ".jpeg")):
        text_parts.append(extract_image_text(file_bytes))

    elif lower_name.endswith(".txt"):
        text_parts.append(file_bytes.decode("utf-8", errors="ignore"))

    return "\n".join([t for t in text_parts if t.strip()])


def parse_llm_json(result_text: str) -> dict:
    """Extract JSON body from LLM response text."""
    start = result_text.find("{")
    end = result_text.rfind("}") + 1
    if start == -1 or end <= start:
        raise ValueError("模型返回不包含有效 JSON")
    return json.loads(result_text[start:end])


