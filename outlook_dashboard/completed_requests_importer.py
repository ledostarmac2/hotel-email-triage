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
    _get_outlook_app,
    _importance_name,
    _limit,
)
from .platform_compat import IS_WINDOWS
from .runtime_log import get_logger
from .text_utils import utc_now_iso

_log = get_logger("completed_requests_importer")

DEFAULT_FOLDER = "Completed Request"
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

    try:
        pythoncom.CoInitialize()
    except Exception as exc:
        raise OutlookDesktopExportError(
            f"Failed to initialize Outlook COM threading: {exc}"
        ) from exc
    try:
        outlook = _get_outlook_app()
        ns = outlook.GetNamespace("MAPI")

        mailbox = _find_named_folder(ns.Folders, mailbox_name)
        if mailbox is None:
            raise OutlookDesktopExportError(f"Mailbox not found: {mailbox_name!r}")

        folder = None

        # 1. Direct child of mailbox root
        try:
            folder = mailbox.Folders.Item(folder_name)
        except Exception:
            pass

        # 2. Inbox → subfolder (documented path: NYCWA_Reservations → Inbox → Completed Request)
        if folder is None:
            try:
                inbox = mailbox.Folders.Item("Inbox")
                folder = inbox.Folders.Item(folder_name)
            except Exception:
                pass

        # 3. GetSharedDefaultFolder — bypasses Exchange Cached Mode for shared mailboxes
        if folder is None:
            try:
                from .config import get_settings
                smtp = get_settings().shared_mailbox_email
                if not smtp:
                    # Auto-resolve SMTP from display name via GAL
                    recipient_probe = ns.CreateRecipient(mailbox_name)
                    recipient_probe.Resolve()
                    if bool(_com_get(recipient_probe, "Resolved", False)):
                        try:
                            ae = recipient_probe.AddressEntry
                            ex_user = ae.GetExchangeUser()
                            if ex_user:
                                smtp = _com_str(ex_user, "PrimarySmtpAddress")
                        except Exception:
                            pass
                        if not smtp:
                            try:
                                smtp = ae.PropertyAccessor.GetProperty(
                                    "http://schemas.microsoft.com/mapi/proptag/0x39FE001E"
                                )
                            except Exception:
                                pass
                if smtp:
                    recipient = ns.CreateRecipient(smtp)
                    recipient.Resolve()
                    if bool(_com_get(recipient, "Resolved", False)):
                        _OL_FOLDER_INBOX = 6
                        shared_inbox = ns.GetSharedDefaultFolder(recipient, _OL_FOLDER_INBOX)
                        folder = shared_inbox.Folders.Item(folder_name)
            except Exception:
                pass

        # 4. GetFolderFromID — derive folder EntryID from a previously-imported email's parent
        #    Works even when Exchange Cached Mode hides the folder from the tree.
        if folder is None:
            try:
                known_entry_id = _get_known_entry_id(db_path)
                if known_entry_id:
                    item = ns.GetItemFromID(known_entry_id)
                    parent = item.Parent
                    if _com_str(parent, "Name") == folder_name:
                        folder = parent
            except Exception:
                pass

        # 5. Search one level inside each top-level folder
        if folder is None:
            for top_idx in range(1, int(_com_get(mailbox.Folders, "Count", 0) or 0) + 1):
                try:
                    top = mailbox.Folders.Item(top_idx)
                    candidate = top.Folders.Item(folder_name)
                    folder = candidate
                    break
                except Exception:
                    continue

        if folder is None:
            raise OutlookDesktopExportError(
                f"Folder {folder_name!r} not found in {mailbox_name!r}."
            )

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
    except Exception as exc:
        _log.warning(
            "completed_requests_importer: could not load processed entry IDs "
            "(dedup unavailable, all emails will be treated as new): %s",
            exc,
        )
        return set()


def _get_known_entry_id(db_path: Path | None) -> str | None:
    """Return any previously-processed EntryID so we can navigate to its parent folder."""
    try:
        with managed_connect(db_path) as db:
            row = db.execute(
                "SELECT outlook_entry_id FROM completed_requests_log WHERE result='dumped' LIMIT 1"
            ).fetchone()
            return str(row["outlook_entry_id"]) if row else None
    except Exception:
        return None
