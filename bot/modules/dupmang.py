from html import escape
from asyncio import sleep, Event

from aiofiles import open as aiopen
from aiofiles.os import remove
from aiofiles.os import path as aiopath
from cloudscraper import create_scraper

from .. import LOGGER, scan_data, bot_cache
from ..core.tg_client import TgClient
from ..core.config_manager import Config
from ..helper.ext_utils.bot_utils import new_task
from ..helper.ext_utils.db_handler import database
from ..helper.ext_utils.status_utils import get_readable_time
from ..helper.ext_utils.task_manager import pre_task_check, mark_scan_start, mark_scan_end, check_scan_running
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.message_utils import (
    delete_message,
    edit_message,
    edit_reply_markup,
    send_file,
    send_message,
)


async def _write_lifetime_dup_file(user_id):
    user_scan = scan_data.get(user_id, {})
    total_dup_map = user_scan.get("total_dup_map", {})
    scanned_chats = user_scan.get("scanned_chats", {})

    lines = []
    lines.append("Duplicate Scanner — Lifetime Duplicate Files")
    lines.append("=" * 52)
    lines.append(f"Total Lifetime Duplicates : {len(total_dup_map)}")
    lines.append(f"Total Scanned Chats       : {len(scanned_chats)}")
    lines.append("")
    if scanned_chats:
        lines.append("Scanned Chats:")
        lines.append("-" * 52)
        for cid, title in scanned_chats.items():
            lines.append(f"  {title} ({cid})")
        lines.append("")
    lines.append(f"{'File Unique ID':<35} {'Message ID'}")
    lines.append("-" * 52)
    for fuid, mid in sorted(total_dup_map.items()):
        lines.append(f"{fuid:<35} {mid}")

    content = "\n".join(lines)
    path = f"/tmp/lifetime_dup_{user_id}.txt"
    async with aiopen(path, "w") as f:
        await f.write(content)
    return path, content


@new_task
async def scan_list(_, message):
    user_id = message.from_user.id
    user_scan = scan_data.get(user_id, {})

    if not user_scan:
        return await send_message(
            message,
            "<b>No Scan Data Found</b>\n"
            "┖ You haven't scanned any chats yet. Use <code>/check -100xxxxxxxxxx</code> to start.",
        )

    scanned_chats   = user_scan.get("scanned_chats", {})
    file_unique_ids = user_scan.get("file_unique_ids", set())
    total_dup_map   = user_scan.get("total_dup_map", {})
    last_chat_id    = user_scan.get("last_scanned_chat_id", None)
    last_chat_title = scanned_chats.get(str(last_chat_id), "N/A") if last_chat_id else "N/A"

    if scanned_chats:
        entries = [f"  ┟ <b>{title}</b> — <code>{cid}</code>" for cid, title in scanned_chats.items()]
        entries[-1] = entries[-1].replace("┟", "┖")
        chat_list_lines = "\n".join(entries)
    else:
        chat_list_lines = "  ┖ None"

    report = (
        "<b>Scan Stats \u2014 Your Database</b>\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        f"\u250f Total Scanned Chats  : <code>{len(scanned_chats)}</code>\n"
        f"\u2503 Total Files Indexed  : <code>{len(file_unique_ids)}</code>\n"
        f"\u2503 Lifetime Duplicates  : <code>{len(total_dup_map)}</code>\n"
        "\u2503\n"
        f"\u2503 Last Scanned Chat    : <b>{last_chat_title}</b>\n"
        "\u2503\n"
        "\u2503 Scanned Chats:\n"
        f"{chat_list_lines}\n"
        "\u2503\n"
        f"\u2517 Lifetime duplicate IDs + message IDs available below."
        "\n\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
    )

    btn = ButtonMaker()
    if total_dup_map:
        btn.data_button("Get Dup List", f"dupmang {user_id} file")
    btn.data_button("Close", f"dupmang {user_id} close")

    await send_message(message, report, btn.build_menu(1 if not total_dup_map else 2))


@new_task
async def dupmang_cb(_, query):
    data = query.data.split()
    message = query.message
    user_id = query.from_user.id
    owner_id = int(data[1])
    action = data[2]

    if user_id != owner_id and not await CustomFilters.sudo("", query):
        return await query.answer("Not Yours!", show_alert=True)

    if action == "file":
        await query.answer("Generating Lifetime Duplicate List..")
        path, _ = await _write_lifetime_dup_file(owner_id)
        btn = ButtonMaker()
        btn.data_button("Dup Display", f"dupmang {owner_id} disp")
        btn.data_button("Web View", f"dupmang {owner_id} web")
        btn.data_button("Close", f"dupmang {owner_id} close")
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
        _, content = await _write_lifetime_dup_file(owner_id)

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
                f"<b>Showing Last {len(res)} Lines from Lifetime Duplicate List:</b>\n\n"
                f"----------<b>START LIST</b>----------\n\n"
                f"<blockquote expandable>{escaped}</blockquote>\n"
                f"----------<b>END LIST</b>----------"
            )

            btn = ButtonMaker()
            btn.data_button("Close", f"dupmang {owner_id} close")

            await send_message(message, text, btn.build_menu(1))
            await edit_reply_markup(message, None)

        except Exception as err:
            LOGGER.error(f"Lifetime Dup Display Error: {err}")

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

        _, content = await _write_lifetime_dup_file(owner_id)

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
async def delete_duplicates(_, message):
    user_id = message.from_user.id

    error_msg, button = await pre_task_check(message)
    if error_msg:
        return await send_message(message, error_msg, button)

    user_scan = scan_data.get(user_id, {})
    chat_dup_map = user_scan.get("chat_dup_map", {})
    scanned_chats = user_scan.get("scanned_chats", {})

    # Filter: only chats that have duplicate entries
    chats_with_dups = {
        cid: title
        for cid, title in scanned_chats.items()
        if chat_dup_map.get(int(cid))
    }

    if not chats_with_dups:
        return await send_message(
            message,
            "<b>No Duplicates Found</b>\n"
            "┖ You have no duplicate entries across any scanned chats.\n"
            "   Run <code>/check -100xxxxxxxxxx</code> to scan a chat first.",
        )

    btn = ButtonMaker()
    for cid, title in chats_with_dups.items():
        dup_count = len(chat_dup_map.get(int(cid), {}))
        btn.data_button(
            f"{title}  [{dup_count} dups]",
            f"deldups {user_id} select {cid}",
        )
    btn.data_button("✖ Close", f"deldups {user_id} close")

    lines = [f"  ┟ <b>{title}</b> — <code>{cid}</code>  [{len(chat_dup_map.get(int(cid), {}))} dups]"
             for cid, title in chats_with_dups.items()]
    lines[-1] = lines[-1].replace("┟", "┖")

    text = (
        "<b>Delete Duplicates — Select Chat</b>\n"
        "────────────────\n"
        "Choose a chat to delete its duplicate messages from:\n\n"
        + "\n".join(lines)
    )

    await send_message(message, text, btn.build_menu(1))


@new_task
async def deldups_cb(_, query):
    data = query.data.split()
    message = query.message
    user_id = query.from_user.id
    owner_id = int(data[1])
    action = data[2]

    if user_id != owner_id and not await CustomFilters.sudo("", query):
        return await query.answer("Not Yours!", show_alert=True)

    if action == "close":
        await query.answer()
        await delete_message(message, message.reply_to_message)

    elif action == "select":
        chat_id = int(data[3])
        user_scan = scan_data.get(owner_id, {})
        chat_dup_map = user_scan.get("chat_dup_map", {})
        scanned_chats = user_scan.get("scanned_chats", {})
        dup_map = chat_dup_map.get(chat_id, {})
        chat_title = scanned_chats.get(str(chat_id), str(chat_id))

        if not dup_map:
            return await query.answer("No duplicates for this chat!", show_alert=True)

        if await check_scan_running(owner_id):
            return await query.answer("Task already running! Please wait for it to complete.", show_alert=True)

        await query.answer(f"Starting deletion for {chat_title}..")

        cancel_event = Event()
        bot_cache.setdefault("scan_cancel", {})[owner_id] = cancel_event
        mark_scan_start(owner_id)

        total = len(dup_map)
        deleted = 0
        failed = 0
        cancelled = False
        from time import time
        start_time = time()
        last_update = time()

        status_msg = await send_message(
            message,
            f"<b>Deleting Duplicates</b>\n"
            f"────────────────\n"
            f"┟ Chat     : <b>{chat_title}</b>\n"
            f"┟ Total    : <code>{total}</code> duplicate messages\n"
            f"┖ Status   : Starting...",
            _delete_cancel_button(owner_id),
        )

        client = TgClient.bot
        items = list(dup_map.items())

        for idx, (fuid, msg_id) in enumerate(items, 1):
            if cancel_event.is_set():
                cancelled = True
                break

            try:
                await client.delete_messages(chat_id, msg_id)
                deleted += 1
            except Exception as e:
                failed += 1
                err_str = str(e)
                LOGGER.warning(f"Delete failed | chat: {chat_id} | msg_id: {msg_id} | err: {err_str}")
                try:
                    msg_link = f"https://t.me/c/{str(chat_id).replace('-100', '')}/{msg_id}"
                    await send_message(
                        message,
                        f"⚠️ <b>Delete Failed</b>\n"
                        f"┟ Message : <a href='{msg_link}'>{msg_id}</a>\n"
                        f"┖ Error   : <code>{err_str}</code>",
                    )
                except Exception:
                    pass

            now = time()
            if now - last_update >= 15:
                last_update = now
                elapsed = now - start_time
                try:
                    await edit_message(
                        status_msg,
                        f"<b>Deleting Duplicates</b>\n"
                        f"────────────────\n"
                        f"┟ Chat      : <b>{chat_title}</b>\n"
                        f"┟ Progress  : <code>{idx}/{total}</code>\n"
                        f"┟ Deleted   : <code>{deleted}</code> ✓\n"
                        f"┟ Failed    : <code>{failed}</code> ✗\n"
                        f"┖ Elapsed   : <code>{get_readable_time(int(elapsed))}</code>",
                        _delete_cancel_button(owner_id),
                    )
                except Exception:
                    pass

            await sleep(1.3)

        mark_scan_end(owner_id)
        bot_cache.get("scan_cancel", {}).pop(owner_id, None)

        elapsed = time() - start_time

        if cancelled:
            for fuid, _ in items[:deleted]:
                chat_dup_map[chat_id].pop(fuid, None)
                user_scan.get("total_dup_map", {}).pop(fuid, None)
            from ..core.config_manager import Config
            if Config.DATABASE_URL:
                await database.update_scan_data(owner_id)
            await delete_message(status_msg)
            return await send_message(
                message,
                f"<b>Deletion Cancelled</b>\n"
                f"────────────────\n"
                f"┟ Chat      : <b>{chat_title}</b>\n"
                f"┟ Deleted   : <code>{deleted}</code> messages\n"
                f"┟ Failed    : <code>{failed}</code>\n"
                f"┟ Remaining : <code>{total - deleted - failed}</code>\n"
                f"┖ Elapsed   : <code>{get_readable_time(int(elapsed))}</code>",
            )

        for fuid, _ in items:
            chat_dup_map[chat_id].pop(fuid, None)
            user_scan.get("total_dup_map", {}).pop(fuid, None)

        from ..core.config_manager import Config
        if Config.DATABASE_URL:
            await database.update_scan_data(owner_id)

        await delete_message(status_msg)
        await send_message(
            message,
            f"<b>Deletion Complete</b>\n"
            f"────────────────\n"
            f"┟ Chat      : <b>{chat_title}</b>\n"
            f"┟ Total     : <code>{total}</code> duplicate messages\n"
            f"┟ Deleted   : <code>{deleted}</code> ✓\n"
            f"┟ Failed    : <code>{failed}</code> ✗\n"
            f"┖ Time      : <code>{get_readable_time(int(elapsed))}</code>",
        )

def _delete_cancel_button(user_id):
    btn = ButtonMaker()
    btn.data_button("✖ Cancel Deletion", f"scancancel {user_id}")
    return btn.build_menu(1)
