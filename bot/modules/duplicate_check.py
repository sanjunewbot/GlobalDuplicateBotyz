from pyrogram.errors import (
    ChatAdminRequired,
    ChannelInvalid,
    ChannelPrivate,
    PeerIdInvalid,
    FloodWait,
)
from asyncio import sleep, Event
from html import escape
from time import time

from aiofiles import open as aiopen
from aiofiles.os import remove
from aiofiles.os import path as aiopath
from cloudscraper import create_scraper

from .. import LOGGER, bot_cache, scan_data
from ..core.config_manager import Config
from ..core.tg_client import TgClient
from ..helper.ext_utils.bot_utils import new_task
from ..helper.ext_utils.db_handler import database
from ..helper.ext_utils.status_utils import get_readable_time, get_scan_status_msg
from ..helper.ext_utils.task_manager import pre_task_check, mark_scan_start, mark_scan_end
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.message_utils import (
    delete_message,
    edit_message,
    edit_reply_markup,
    send_file,
    send_message,
)


def _cancel_button(user_id):
    btn = ButtonMaker()
    btn.data_button("Cancel Scan", f"scancancel {user_id}")
    return btn.build_menu(1)


def _dup_list_button(user_id):
    btn = ButtonMaker()
    btn.data_button("Get Duplicate List", f"duplist {user_id} file")
    return btn.build_menu(1)


async def _write_dup_file(user_id):
    user_scan = scan_data.get(user_id, {})
    last_dup_map = user_scan.get("last_dup_map", {})
    scanned_chats = user_scan.get("scanned_chats", {})
    last_chat_id = user_scan.get("last_scanned_chat_id", "")
    last_chat_title = scanned_chats.get(str(last_chat_id), str(last_chat_id))

    lines = []
    lines.append("Duplicate Scanner — Duplicate Files (Last Scan)")
    lines.append("=" * 48)
    lines.append(f"Chat            : {last_chat_title} ({last_chat_id})")
    lines.append(f"Total Duplicates: {len(last_dup_map)}")
    lines.append("")
    lines.append(f"{'File Unique ID':<35} {'Message ID'}")
    lines.append("-" * 48)
    for fuid, mid in sorted(last_dup_map.items()):
        lines.append(f"{fuid:<35} {mid}")

    content = "\n".join(lines)
    path = f"/tmp/dup_list_{user_id}.txt"
    async with aiopen(path, "w") as f:
        await f.write(content)
    return path, content

@new_task
async def check_duplicates(_, message):
    user_id = message.from_user.id
    args = message.command

    error_msg, button = await pre_task_check(message)
    if error_msg:
        return await send_message(message, error_msg, button)

    if len(args) < 2:
        return await send_message(
            message,
            "<b>Invalid Usage</b>\n"
            "┖ <code>/check -100xxxxxxxxxx</code>",
        )

    raw_id = args[1].strip()
    try:
        chat_id = int(raw_id)
    except ValueError:
        return await send_message(
            message,
            "<b>Invalid Chat ID</b>\n"
            f"┖ <code>{raw_id}</code> is not a valid integer ID.",
        )

    client = TgClient.user
    if client is None:
        return await send_message(
            message,
            "<b>User Session Not Found</b>\n"
            "┟ Set <code>USER_SESSION_STRING</code> in config.\n"
            "┖ Bots cannot read chat history — a user session is required.",
        )

    cancel_event = Event()
    bot_cache.setdefault("scan_cancel", {})[user_id] = cancel_event

    mark_scan_start(user_id)

    status_msg = await send_message(
        message,
        "<b>Duplicate Scanner</b>\n"
        "────────────────\n"
        f"┟ Chat ID : <code>{chat_id}</code>\n"
        "┖ Status  : Initialising...",
        _cancel_button(user_id),
    )

    try:
        chat = await client.get_chat(chat_id)
        chat_title = chat.title or str(chat_id)
    except (PeerIdInvalid, ChannelInvalid, ChannelPrivate):
        mark_scan_end(user_id)
        bot_cache["scan_cancel"].pop(user_id, None)
        return await edit_message(
            status_msg,
            "<b>Access Denied</b>\n"
            f"┟ Chat ID : <code>{chat_id}</code>\n"
            "┖ Make sure the user account is a member of that chat.",
        )
    except Exception as e:
        mark_scan_end(user_id)
        bot_cache["scan_cancel"].pop(user_id, None)
        return await edit_message(
            status_msg,
            "<b>Error Fetching Chat</b>\n"
            f"┖ <code>{e}</code>",
        )

    existing_ids = scan_data.get(user_id, {}).get("file_unique_ids", set())
    existing_count = len(existing_ids)

    await edit_message(
        status_msg,
        "<b>Duplicate Scanner</b>\n"
        "────────────────\n"
        f"┟ Chat          : <b>{chat_title}</b>\n"
        f"┟ Pre-Indexed   : <code>{existing_count}</code> files already in your database\n"
        "┖ Status        : Starting scan...",
        _cancel_button(user_id),
    )

    total = 0
    new_ids = set()
    dup_map = {}
    dup_entries = 0
    cross_dup = 0
    cancelled = False
    start_time = time()
    last_update = time()

    try:
        async for msg in client.get_chat_history(chat_id):
            if cancel_event.is_set():
                cancelled = True
                break

            total += 1

            media = (
                msg.document
                or msg.video
                or msg.audio
                or msg.photo
                or msg.animation
                or msg.voice
                or msg.video_note
                or msg.sticker
            )

            if media and hasattr(media, "file_unique_id"):
                fuid = media.file_unique_id
                if fuid in existing_ids:
                    cross_dup += 1
                    dup_map[fuid] = msg.id
                elif fuid in new_ids:
                    dup_entries += 1
                    dup_map[fuid] = msg.id
                else:
                    new_ids.add(fuid)

            now = time()
            if now - last_update >= 15:
                last_update = now
                elapsed = now - start_time
                try:
                    await edit_message(
                        status_msg,
                        get_scan_status_msg(
                            chat_title, chat_id, total,
                            new_ids, dup_entries, cross_dup,
                            existing_count, elapsed,
                        ),
                        _cancel_button(user_id),
                    )
                except Exception:
                    pass

            if total % 500 == 0:
                await sleep(0.1)

    except ChatAdminRequired:
        mark_scan_end(user_id)
        bot_cache["scan_cancel"].pop(user_id, None)
        return await edit_message(
            status_msg,
            "<b>Permission Error</b>\n"
            f"┖ User account must be a member of <b>{chat_title}</b>.",
        )
    except FloodWait as fw:
        await sleep(fw.value)
    except Exception as e:
        LOGGER.error(f"Duplicate Check Error: {e}")
        mark_scan_end(user_id)
        bot_cache["scan_cancel"].pop(user_id, None)
        return await edit_message(
            status_msg,
            "<b>Scan Failed</b>\n"
            f"┖ <code>{e}</code>",
        )
    finally:
        mark_scan_end(user_id)
        bot_cache["scan_cancel"].pop(user_id, None)

    if cancelled:
        elapsed = time() - start_time
        total_dupes = dup_entries + cross_dup
        LOGGER.info(
            f"Scan Cancelled | User: {user_id} | Chat: {chat_title} ({chat_id}) | "
            f"Scanned: {total} msgs | Elapsed: {get_readable_time(int(elapsed))} | "
            f"Dupes Found: {total_dupes} | Data NOT saved"
        )
        await delete_message(status_msg)
        return await send_message(
            message,
            "<b>Scan Cancelled</b>\n"
            "────────────────\n"
            f"┟ Chat          : <b>{chat_title}</b>\n"
            f"┟ Scanned       : <code>{total}</code> messages\n"
            f"┟ Time Elapsed  : <code>{get_readable_time(int(elapsed))}</code>\n"
            f"┟ Dupes Found   : <code>{total_dupes}</code>\n"
            "┖ Data from this partial scan has not been saved.",
        )

    user_scan = scan_data.setdefault(user_id, {
        "file_unique_ids": set(),
        "scanned_chats": {},
        "total_dup_map": {},
        "chat_dup_map": {},
        "chat_file_ids": {},
    })

    user_scan["file_unique_ids"].update(new_ids)
    user_scan["scanned_chats"][str(chat_id)] = chat_title
    user_scan["total_dup_map"].update(dup_map)

    chat_dup_map = user_scan.setdefault("chat_dup_map", {})
    if chat_id not in chat_dup_map:
        chat_dup_map[chat_id] = {}
    chat_dup_map[chat_id].update(dup_map)

    chat_file_ids = user_scan.setdefault("chat_file_ids", {})
    if chat_id not in chat_file_ids:
        chat_file_ids[chat_id] = set()
    chat_file_ids[chat_id].update(new_ids)

    user_scan["last_dup_map"] = dup_map
    user_scan["last_scanned_chat_id"] = chat_id

    if Config.DATABASE_URL:
        await database.update_scan_data(user_id)

    total_media = len(new_ids) + dup_entries + cross_dup
    total_dupes = dup_entries + cross_dup
    total_db = len(user_scan.get("file_unique_ids", set()))
    elapsed = time() - start_time

    if total_dupes == 0:
        dup_line = "┃ No duplicate files found in this chat."
    else:
        dup_line = (
            f"┃ {dup_entries} file(s) repeated within this chat.\n"
            f"┃ {cross_dup} file(s) matched your previously scanned chats.\n"
            f"┃ Total {total_dupes} duplicate file(s) detected."
        )

    report = (
        "<b>Scan Complete \u2014 Duplicate Report</b>\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        f"\u250f Chat              : <b>{chat_title}</b>\n"
        f"\u2503 Chat ID           : <code>{chat_id}</code>\n"
        "\u2503\n"
        f"\u2503 Time Taken        : <code>{get_readable_time(int(elapsed))}</code>\n"
        f"\u2503 Messages Scanned  : <code>{total}</code>\n"
        f"\u2503 Media Files Found : <code>{total_media}</code>\n"
        f"\u2503 New Files Indexed : <code>{len(new_ids)}</code>\n"
        "\u2503\n"
        f"{dup_line}\n"
        "\u2503\n"
        f"\u2517 Your Total Indexed Files : <code>{total_db}</code>"
        "\n\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
    )

    await delete_message(status_msg)

    if total_dupes == 0:
        await send_message(message, report)
    else:
        await send_message(message, report, _dup_list_button(user_id))
        
@new_task
async def dup_list_cb(_, query):
    data = query.data.split()
    message = query.message
    user_id = query.from_user.id
    owner_id = int(data[1])
    action = data[2]

    if user_id != owner_id and not await CustomFilters.sudo("", query):
        return await query.answer("Not Yours!", show_alert=True)

    if action == "file":
        await query.answer("Generating Duplicate List..")
        path, _ = await _write_dup_file(owner_id)
        btn = ButtonMaker()
        btn.data_button("Dup Display", f"duplist {owner_id} disp")
        btn.data_button("Web View", f"duplist {owner_id} web")
        btn.data_button("Close", f"duplist {owner_id} close")
        await send_file(message, path, buttons=btn.build_menu(2))
        try:
            if await aiopath.exists(path):
                await remove(path)
        except Exception:
            pass

    elif action == "close":
        await query.answer()
        await delete_message(message, message.reply_to_message)

    elif action == "disp":
        await query.answer("Fetching List..")
        _, content = await _write_dup_file(owner_id)

        try:
            res, total = [], 0
            for line in reversed(content.splitlines()):
                res.append(line)
                total += len(line) + 1
                if total > 3500:
                    break

            list_content = "\n".join(reversed(res))
            escaped = escape(list_content)

            text = (
                f"<b>Showing Last {len(res)} Lines from Duplicate List:</b>\n\n"
                f"----------<b>START LIST</b>----------\n\n"
                f"<blockquote expandable>{escaped}</blockquote>\n"
                f"----------<b>END LIST</b>----------"
            )

            btn = ButtonMaker()
            btn.data_button("Close", f"duplist {owner_id} close")

            await send_message(message, text, btn.build_menu(1))
            await edit_reply_markup(message, None)

        except Exception as err:
            LOGGER.error(f"Dup List Display Error: {err}")

    elif action == "web":
        boundary = "R1eFDeaC554BUkLF"

        headers = {
            "Content-Type": f"multipart/form-data; boundary=----WebKitFormBoundary{boundary}",
            "Origin": "https://spaceb.in",
            "Referer": "https://spaceb.in/",
            "sec-ch-ua": '"Not-A.Brand";v="99", "Chromium";v="124"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
        }

        _, content = await _write_dup_file(owner_id)

        post_data = (
            f"------WebKitFormBoundary{boundary}\r\n"
            f'Content-Disposition: form-data; name="content"\r\n\r\n'
            f"{content}\r\n"
            f"------WebKitFormBoundary{boundary}--\r\n"
        )

        cget = create_scraper().request
        resp = cget("POST", "https://spaceb.in/", headers=headers, data=post_data)

        if resp.status_code == 200:
            await query.answer("Generating..")
            btn = ButtonMaker()
            btn.url_button("📨 Web Paste (SB)", resp.url)
            await edit_reply_markup(message, btn.build_menu(1))
        else:
            await query.answer("Web Paste Failed! Check Logs", show_alert=True)


@new_task
async def scan_cancel_cb(_, query):
    user_id = query.from_user.id
    data = query.data.split()
    owner_id = int(data[1])

    if user_id != owner_id and not await CustomFilters.sudo("", query):
        return await query.answer("This is not your scan!", show_alert=True)

    cancel_events = bot_cache.get("scan_cancel", {})
    if owner_id not in cancel_events:
        return await query.answer("No active scan found or already completed.", show_alert=True)

    cancel_events[owner_id].set()
    await query.answer("Scan cancellation requested.", show_alert=True)
