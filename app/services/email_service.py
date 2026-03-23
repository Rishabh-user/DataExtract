"""Email service with HTML templates. Uses dummy backend by default (logs to console + file)."""

import json
import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Directory where dummy emails are saved as .html files
DUMMY_EMAIL_DIR = Path("email_logs")


# ─── HTML Templates ──────────────────────────────────────────────────────────

def _base_template(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           background:#f4f7fb; margin:0; padding:24px; }}
    .wrapper {{ max-width:600px; margin:0 auto; }}
    .header {{ background:#2563eb; color:#fff; padding:28px 32px; border-radius:10px 10px 0 0; }}
    .header h1 {{ margin:0; font-size:1.4rem; }}
    .header p {{ margin:6px 0 0; opacity:0.85; font-size:0.9rem; }}
    .body {{ background:#fff; padding:28px 32px; border:1px solid #e2e8f0; }}
    .footer {{ background:#f8fafc; border:1px solid #e2e8f0; border-top:none;
               padding:16px 32px; border-radius:0 0 10px 10px; text-align:center;
               font-size:0.8rem; color:#94a3b8; }}
    .btn {{ display:inline-block; background:#2563eb; color:#fff; padding:10px 22px;
            border-radius:6px; text-decoration:none; font-weight:600; margin-top:12px; }}
    .badge {{ display:inline-block; padding:3px 10px; border-radius:12px;
              font-size:0.78rem; font-weight:600; }}
    .badge-success {{ background:#dcfce7; color:#16a34a; }}
    .badge-info {{ background:#dbeafe; color:#2563eb; }}
    table {{ width:100%; border-collapse:collapse; margin-top:16px; }}
    th {{ background:#f1f5f9; text-align:left; padding:8px 12px; font-size:0.8rem;
          text-transform:uppercase; color:#64748b; }}
    td {{ padding:8px 12px; border-bottom:1px solid #f1f5f9; font-size:0.9rem; }}
    .key-box {{ background:#1e293b; color:#38bdf8; padding:14px 18px;
                border-radius:6px; font-family:monospace; font-size:0.9rem;
                word-break:break-all; margin-top:12px; }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>DataExtract Platform</h1>
      <p>{title}</p>
    </div>
    <div class="body">{body_html}</div>
    <div class="footer">
      © {datetime.utcnow().year} DataExtract Platform &nbsp;|&nbsp;
      This is an automated message — please do not reply.
    </div>
  </div>
</body>
</html>"""


def _template_extraction_summary(data: dict[str, Any]) -> tuple[str, str]:
    doc = data.get("document", {})
    pages = data.get("pages", [])
    file_name = doc.get("file_name", "—")
    file_type = doc.get("file_type", "—")
    source = doc.get("source") or "—"
    status = doc.get("status", "—")
    page_count = len(pages)
    snippet = pages[0].get("content", "")[:300] + ("…" if len(pages[0].get("content", "")) > 300 else "") if pages else "No content extracted."

    subject = f"Extraction Complete: {file_name}"
    body = f"""
    <h2 style="margin-top:0">Extraction Summary</h2>
    <p>Your document has been successfully processed by DataExtract.</p>
    <table>
      <tr><th>Field</th><th>Value</th></tr>
      <tr><td>File Name</td><td><strong>{file_name}</strong></td></tr>
      <tr><td>File Type</td><td>{file_type}</td></tr>
      <tr><td>Source</td><td>{source}</td></tr>
      <tr><td>Status</td><td><span class="badge badge-success">{status}</span></td></tr>
      <tr><td>Pages / Sections</td><td>{page_count}</td></tr>
    </table>
    <h3 style="margin-top:24px">Content Preview</h3>
    <div style="background:#f8fafc;padding:14px;border-radius:6px;
                font-family:monospace;font-size:0.85rem;white-space:pre-wrap;
                border:1px solid #e2e8f0;">{snippet}</div>
    <p style="margin-top:24px">
      <a href="http://localhost:{settings.PORT}/view/{doc.get('id','')}" class="btn">View Full Extraction</a>
    </p>"""
    return subject, _base_template(subject, body)


def _template_api_key_created(data: dict[str, Any]) -> tuple[str, str]:
    project = data.get("project_name", "—")
    key_preview = data.get("api_key_preview", "")
    actions = data.get("actions", [])
    file_types = data.get("file_types", ["*"])

    subject = f"New API Key Generated: {project}"
    body = f"""
    <h2 style="margin-top:0">API Key Generated</h2>
    <p>A new API key has been created for project <strong>{project}</strong>.</p>
    <h3>Your API Key</h3>
    <div class="key-box">{key_preview}</div>
    <p style="color:#dc2626;font-size:0.85rem;margin-top:8px;">
      ⚠️ Store this key securely. It will not be shown again.
    </p>
    <h3 style="margin-top:20px">Permissions</h3>
    <table>
      <tr><th>Setting</th><th>Value</th></tr>
      <tr><td>Allowed Actions</td><td>{', '.join(actions) if actions else 'All'}</td></tr>
      <tr><td>Allowed File Types</td><td>{', '.join(file_types) if file_types != ['*'] else 'All types'}</td></tr>
    </table>
    <p style="margin-top:24px">Include this key in every API request as a header:</p>
    <div class="key-box">x-api-key: {key_preview}</div>"""
    return subject, _base_template(subject, body)


def _template_welcome(data: dict[str, Any]) -> tuple[str, str]:
    subject = "Welcome to DataExtract Platform"
    body = f"""
    <h2 style="margin-top:0">Welcome to DataExtract!</h2>
    <p>Your Universal Data Extraction Platform is ready to use.</p>
    <h3>Quick Start</h3>
    <ol>
      <li>Generate an API key at <a href="http://localhost:{settings.PORT}/keys">Keys page</a></li>
      <li>Upload a document at <a href="http://localhost:{settings.PORT}/">Upload page</a></li>
      <li>View extracted data at <a href="http://localhost:{settings.PORT}/documents">Documents page</a></li>
    </ol>
    <h3>Supported Formats</h3>
    <table>
      <tr><th>Format</th><th>Extensions</th></tr>
      <tr><td>PDF</td><td>.pdf</td></tr>
      <tr><td>Excel</td><td>.xlsx, .xls</td></tr>
      <tr><td>Word</td><td>.docx, .doc</td></tr>
      <tr><td>Email</td><td>.eml, .msg</td></tr>
      <tr><td>CSV</td><td>.csv</td></tr>
      <tr><td>PowerPoint</td><td>.pptx, .ppt</td></tr>
      <tr><td>Image (OCR)</td><td>.png, .jpg, .jpeg, .tiff, .bmp</td></tr>
    </table>
    <p style="margin-top:24px">
      <a href="http://localhost:{settings.PORT}/" class="btn">Open Platform</a>
    </p>"""
    return subject, _base_template(subject, body)


_TEMPLATES = {
    "extraction_summary": _template_extraction_summary,
    "api_key_created": _template_api_key_created,
    "welcome": _template_welcome,
}


# ─── Service ─────────────────────────────────────────────────────────────────

class EmailService:
    def render(self, template: str, data: dict[str, Any]) -> tuple[str, str]:
        """Return (subject, html_body) for the given template name."""
        fn = _TEMPLATES.get(template)
        if not fn:
            raise ValueError(f"Unknown email template: '{template}'. Available: {list(_TEMPLATES)}")
        return fn(data)

    async def send(
        self,
        to: str,
        template: str,
        data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        subject, html = self.render(template, data or {})

        if settings.EMAIL_BACKEND == "smtp":
            return await self._send_smtp(to, subject, html)
        else:
            return self._send_dummy(to, subject, html)

    def _send_dummy(self, to: str, subject: str, html: str) -> dict[str, Any]:
        """Log email to console and save to email_logs/ directory."""
        DUMMY_EMAIL_DIR.mkdir(exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        fname = f"{timestamp}_{to.replace('@','_at_').replace('.','_')}.html"
        fpath = DUMMY_EMAIL_DIR / fname
        fpath.write_text(html, encoding="utf-8")

        logger.info(
            "📧 [DUMMY EMAIL] To: %s | Subject: %s | Saved: %s",
            to, subject, fpath,
        )
        return {
            "success": True,
            "message": f"Email logged (dummy backend). Saved to {fpath}",
            "backend": "dummy",
        }

    async def _send_smtp(self, to: str, subject: str, html: str) -> dict[str, Any]:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
            msg["To"] = to
            msg.attach(MIMEText(html, "html"))

            with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
                if settings.EMAIL_USE_TLS:
                    server.starttls()
                if settings.EMAIL_USERNAME and settings.EMAIL_PASSWORD:
                    server.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
                server.sendmail(settings.EMAIL_FROM, [to], msg.as_string())

            logger.info("Email sent to %s: %s", to, subject)
            return {"success": True, "message": f"Email sent to {to}", "backend": "smtp"}
        except Exception as e:
            logger.error("SMTP send failed: %s", e)
            return {"success": False, "message": str(e), "backend": "smtp"}


email_service = EmailService()
