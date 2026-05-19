"""Read emails from the 'Completed Requests' Outlook folder for training.

READ-ONLY: never sends, deletes, moves, or mutates any Outlook message.
Imports up to batch_size messages that have not yet been processed by the
completed-requests training pipeline, tracking them by Outlook EntryID.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .database import managed_connect
from .outlook_desktop import (
    OutlookDesktopExportError,
    _MAX_BODY_CHARS,
    _OL_MAIL_ITEM,
    _clean_preview,
    _com_get,
    _com_str,
    _find_named_folder,
    _format_datetime,
    _importance_name,
    _limit,
)
from .platform_compat import IS_WINDOWS
from .runtime_log import get_logger
from .text_utils import utc_now_iso

_log = get_logger("completed_requests_importer")

DEFAULT_FOLDER = "Completed Requests"
DEFAULT_BATCH_SIZE = 50


def read_completed_requests(
    mailbox_name: str,
    folder_name: str = DEFAULT_FOLDER,
    batch_size: int = DEFAULT_BATCH_SIZE,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Read up to batch_size unprocessed emails from the Completed Requests folder.

    Args:
        mailbox_name: Display name of the Outlook mailbox (e.g. the shared inbox name).
        folder_name: Sub-folder to read from (default: "Completed Requests").
        batch_size: Max new messages to return per call.
        db_path: Override SQLite path (tests/dev).

    Returns:
        {messages, checked_count, new_count, skipped_count, folder, mailbox}
    """
    if not IS_WINDOWS:
        raise OutlookDesktopExportError("Outlook COM integration is Windows-only.")

    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise OutlookDesktopExportError("pywin32 is not available.") from exc

    already_processed = _load_processed_entry_ids(db_path)

    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        ns = outlook.GetNamespace("MAPI")

        mailbox = _find_named_folder(ns.Folders, mailbox_name)
        if mailbox is None:
            raise OutlookDesktopExportError(f"Mailbox not found: {mailbox_name!r}")

        try:
            folder = mailbox.Folders.Item(folder_name)
        except Exception as exc:
            raise OutlookDesktopExportError(
                f"Folder {folder_name!r} not found in {mailbox_name!r}."
            ) from exc

        items = folder.Items
        try:
            items.Sort("[ReceivedTime]", True)
        except Exception:
            pass

        checked_count = int(_com_get(items, "Count", 0) or 0)
        messages: list[dict[str, Any]] = []
        skipped_count = 0

        for index in range(1, checked_count + 1):
            if len(messages) >= batch_size:
                break
            try:
                item = items.Item(index)
            except Exception:
                skipped_count += 1
                continue

            if int(_com_get(item, "Class", 0) or 0) != _OL_MAIL_ITEM:
                skipped_count += 1
                continue

            entry_id = _com_str(item, "EntryID")
            if not entry_id or entry_id in already_processed:
                skipped_count += 1
                continue

            try:
                payload = _item_to_payload(item)
            except Exception:
                skipped_count += 1
                continue

            messages.append(payload)

        _log.info(
            "completed_requests_importer: folder=%r checked=%d new=%d skipped=%d",
            folder_name,
            checked_count,
            len(messages),
            skipped_count,
        )
        return {
            "mailbox": mailbox_name,
            "folder": folder_name,
            "checked_count": checked_count,
            "new_count": len(messages),
            "skipped_count": skipped_count,
            "messages": messages,
        }
    except OutlookDesktopExportError:
        raise
    except Exception as exc:
        raise OutlookDesktopExportError(f"Could not read Outlook: {exc}") from exc
    finally:
        pythoncom.CoUninitialize()


def mark_processed(
    outlook_entry_id: str,
    result: str,
    subject_tokens: str | None = None,
    sender_domain: str | None = None,
    db_path: Path | None = None,
) -> None:
    """Record that an Outlook entry from Completed Requests has been processed."""
    with managed_connect(db_path) as db:
        db.execute(
            """
            INSERT OR IGNORE INTO completed_requests_log
                (outlook_entry_id, subject_tokens, sender_domain, result, processed_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (outlook_entry_id, subject_tokens, sender_domain, result, utc_now_iso()),
        )


# ── helpers ───────────────────────────────────────────────────────────────────

def _item_to_payload(item) -> dict[str, Any]:
    body = _limit(_com_str(item, "Body"), _MAX_BODY_CHARS)
    received = _com_get(item, "ReceivedTime")
    entry_id = _com_str(item, "EntryID")
    return {
        "outlook_entry_id": entry_id,
        "graph_message_id": entry_id,
        "subject": _com_str(item, "Subject"),
        "sender_name": _com_str(item, "SenderName"),
        "sender_email": _com_str(item, "SenderEmailAddress"),
        "from_name": _com_str(item, "SenderName"),
        "from_email": _com_str(item, "SenderEmailAddress"),
        "received_datetime": _format_datetime(received),
        "body_preview": _limit(_clean_preview(body), 240),
        "body_content_type": "text",
        "body_content": body,
        "body_text": body,
        "conversation_id": _com_str(item, "ConversationID"),
        "importance": _importance_name(_com_get(item, "Importance", 1)),
        "has_attachments": int(_com_get(_com_get(item, "Attachments"), "Count", 0) or 0) > 0,
        "source": "completed_requests",
        "mailbox_mode": "shared",
    }


def _load_processed_entry_ids(db_path: Path | None) -> set[str]:
    try:
        with managed_connect(db_path) as db:
            rows = db.execute(
                "SELECT outlook_entry_id FROM completed_requests_log"
            ).fetchall()
            return {str(r["outlook_entry_id"]) for r in rows}
    except Exception:
        return set()
