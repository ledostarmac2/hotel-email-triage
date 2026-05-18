from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from .platform_compat import IS_WINDOWS

try:
    import winreg
except ImportError:  # pragma: no cover - Windows-only module
    winreg = None


_MAX_BODY_CHARS = 16000
_OL_MAIL_ITEM = 43
_OL_MSG = 3


class OutlookDesktopExportError(RuntimeError):
    pass


class _PyWin32Unavailable(OutlookDesktopExportError):
    pass


def export_mailbox_folder_to_msg(
    mailbox_name: str,
    folder_name: str,
    export_root: Path,
    macro_name: str,
) -> dict[str, object]:
    if not IS_WINDOWS:
        raise OutlookDesktopExportError("Outlook COM integration is Windows-only.")
    export_root.mkdir(parents=True, exist_ok=True)
    try:
        return _export_mailbox_with_pywin32(mailbox_name, folder_name, export_root)
    except _PyWin32Unavailable as exc:
        result = _start_outlook_autorun(
            macro_name,
            "pywin32 is unavailable, so ReplyRight started classic Outlook with /autorun.",
        )
        result["direct_import_error"] = str(exc)
        return result


def _export_mailbox_with_pywin32(mailbox_name: str, folder_name: str, export_root: Path) -> dict[str, object]:
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise _PyWin32Unavailable("Outlook COM not available on this platform.") from exc

    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        mailbox = _find_named_folder(namespace.Folders, mailbox_name)
        if mailbox is None:
            raise OutlookDesktopExportError(f"Could not find Outlook mailbox: {mailbox_name}")

        try:
            folder = mailbox.Folders.Item(folder_name)
        except Exception as exc:
            raise OutlookDesktopExportError(
                f"Could not find Outlook folder '{folder_name}' in mailbox '{mailbox_name}'."
            ) from exc

        export_dir = export_root / _clean_file_name(mailbox_name) / _clean_file_name(folder_name)
        export_dir.mkdir(parents=True, exist_ok=True)

        # Wipe stale .msg files before each import so the folder mirrors
        # the current Outlook inbox exactly and never accumulates orphans.
        for _old in export_dir.glob("*.msg"):
            _old.unlink(missing_ok=True)

        messages, checked_count, saved_count, skipped_count = _read_mail_items(folder, export_dir)

        return {
            "mailbox": mailbox_name,
            "folder": folder_name,
            "export_dir": str(export_dir),
            "checked_count": checked_count,
            "exported_count": len(messages),
            "saved_msg_count": saved_count,
            "skipped_count": skipped_count,
            "launched_macro": False,
            "launch_method": "pywin32-com",
            "messages": messages,
            "stdout": f"Read {len(messages)} Outlook messages directly through read-only COM.",
        }
    except OutlookDesktopExportError:
        raise
    except Exception as exc:
        raise OutlookDesktopExportError(f"Could not read Outlook through COM: {exc}") from exc
    finally:
        pythoncom.CoUninitialize()


def _read_mail_items(folder, export_dir: Path) -> tuple[list[dict[str, object]], int, int, int]:
    items = folder.Items
    try:
        items.Sort("[ReceivedTime]", True)
    except Exception:
        pass

    checked_count = int(_com_get(items, "Count", 0) or 0)
    messages: list[dict[str, object]] = []
    saved_count = 0
    skipped_count = 0

    for index in range(1, checked_count + 1):
        try:
            item = items.Item(index)
        except Exception:
            skipped_count += 1
            continue

        if int(_com_get(item, "Class", 0) or 0) != _OL_MAIL_ITEM:
            skipped_count += 1
            continue

        try:
            message = _mail_item_to_payload(item)
        except Exception:
            skipped_count += 1
            continue

        if not message.get("graph_message_id"):
            skipped_count += 1
            continue

        if _save_msg_copy(item, export_dir, index):
            saved_count += 1
        messages.append(message)

    return messages, checked_count, saved_count, skipped_count


def _mail_item_to_payload(item) -> dict[str, object]:
    body = _limit(_com_str(item, "Body"), _MAX_BODY_CHARS)
    received = _com_get(item, "ReceivedTime")
    return {
        "graph_message_id": _com_str(item, "EntryID"),
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
        "source": "outlook_desktop",
        "mailbox_mode": "shared",
    }


def _save_msg_copy(item, export_dir: Path, index: int) -> bool:
    received = _safe_file_datetime(_com_get(item, "ReceivedTime"))
    subject = _clean_file_name(_com_str(item, "Subject")) or "No Subject"
    file_path = _bounded_msg_path(export_dir, received, subject, index)
    if file_path.exists():
        return False
    try:
        item.SaveAs(str(file_path), _OL_MSG)
    except Exception:
        return False
    return True


def _bounded_msg_path(export_dir: Path, received: str, subject: str, index: int) -> Path:
    subject = subject[:80]
    file_path = export_dir / f"{received}_{subject}_{index}.msg"
    while len(str(file_path)) > 245 and len(subject) > 12:
        subject = subject[:-8].rstrip()
        file_path = export_dir / f"{received}_{subject}_{index}.msg"
    return file_path


def _find_named_folder(folders, name: str):
    target = name.casefold()
    count = int(_com_get(folders, "Count", 0) or 0)
    for index in range(1, count + 1):
        try:
            folder = folders.Item(index)
        except Exception:
            continue
        if _com_str(folder, "Name").casefold() == target:
            return folder
    return None


def _start_outlook_autorun(macro_name: str, reason: str) -> dict[str, object]:
    if not macro_name:
        raise OutlookDesktopExportError("Outlook macro name is not configured.")

    outlook_exe = _find_outlook_exe()
    if not outlook_exe:
        raise OutlookDesktopExportError(
            "Could not locate classic Outlook for Windows. "
            "Open classic Outlook once, then try Refresh Inbox again."
        )

    try:
        subprocess.Popen(
            [outlook_exe, "/autorun", macro_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise OutlookDesktopExportError(f"Could not start Outlook: {exc}") from exc

    return {
        "mailbox": None,
        "folder": None,
        "export_dir": None,
        "checked_count": None,
        "exported_count": None,
        "skipped_count": None,
        "launched_macro": True,
        "launch_method": "outlook-autorun",
        "macro": macro_name,
        "stdout": f"{reason} Path: {outlook_exe}",
    }


def _find_outlook_exe() -> str | None:
    candidates: list[str] = []
    candidates.extend(_registry_outlook_paths())

    command_path = shutil.which("OUTLOOK.EXE") or shutil.which("outlook.exe")
    if command_path:
        candidates.append(command_path)

    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if not base:
            continue
        for relative in (
            r"Microsoft Office\root\Office16\OUTLOOK.EXE",
            r"Microsoft Office\root\Office15\OUTLOOK.EXE",
            r"Microsoft Office\Office16\OUTLOOK.EXE",
            r"Microsoft Office\Office15\OUTLOOK.EXE",
        ):
            candidates.append(str(Path(base) / relative))

    seen: set[str] = set()
    for candidate in candidates:
        normalized = os.path.normcase(os.path.abspath(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)
        if Path(candidate).exists():
            return candidate
    return None


def _registry_outlook_paths() -> list[str]:
    if winreg is None:
        return []

    key_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE"),
    ]
    views = [0]
    for flag_name in ("KEY_WOW64_64KEY", "KEY_WOW64_32KEY"):
        flag = getattr(winreg, flag_name, None)
        if flag is not None:
            views.append(flag)

    values: list[str] = []
    for root, key_path in key_paths:
        for view in views:
            try:
                with winreg.OpenKey(root, key_path, 0, winreg.KEY_READ | view) as key:
                    value, _ = winreg.QueryValueEx(key, "")
            except OSError:
                continue
            if value:
                values.append(str(value))
    return values


def _com_get(obj, attr: str, default=None):
    if obj is None:
        return default
    try:
        return getattr(obj, attr)
    except Exception:
        return default


def _com_str(obj, attr: str) -> str:
    value = _com_get(obj, attr, "")
    if value is None:
        return ""
    return str(value)


def _importance_name(value) -> str:
    try:
        importance = int(value)
    except (TypeError, ValueError):
        importance = 1
    if importance == 2:
        return "high"
    if importance == 0:
        return "low"
    return "normal"


def _format_datetime(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%dT%H:%M:%S")
    return str(value)


def _safe_file_datetime(value) -> str:
    if value is None:
        return "unknown-date"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d_%H-%M-%S")
    return _clean_file_name(str(value)) or "unknown-date"


def _clean_preview(value: str) -> str:
    return " ".join(value.replace("\r", " ").replace("\n", " ").replace("\t", " ").split())


def _clean_file_name(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", value)
    return cleaned.strip()


def _limit(value: str, max_chars: int) -> str:
    return value[:max_chars] if value else ""
