from asyncio import sleep, Event
from time import time

from .. import LOGGER, scan_data, bot_cache
from ..core.tg_client import TgClient
from ..core.config_manager import Config
from ..helper.ext_utils.bot_utils import new_task
from ..helper.ext_utils.db_handler import database
from ..helper.ext_utils.status_utils import get_readable_time
from ..helper.ext_utils.task_manager import (
    pre_task_check,
    mark_scan_start,
    mark_scan_end,
    check_scan_running,
)
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.message_utils import (
    delete_message,
    edit_message,
    send_message,
)


def _udlt_cancel_button(user_id):
    btn = ButtonMaker()
    btn.data_button("✖ Cancel Deletion", f"scancancel {user_id}")
    return btn.build_menu(1)


@new_task
async def user_delete_duplicates(_, message):
    user_id = message.from_user.id

    error_msg, button = await pre_task_check(message)
    if error_msg:
        return await send_message(message, error_msg, button)

    client = TgClient.user
    if client is None:
        return await send_message(
            message,
            "<b>User Session Not Found</b>\n"
            "┟ Set <code>USER_SESSION_STRING</code> in config.\n"
            "┖ This command requires a user session to delete messages.",
        )

    user_scan = scan_data.get(user_id, {})
    chat_dup_map = user_scan.get("chat_dup_map", {})
    scanned_chats = user_scan.get("scanned_chats", {})

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
            f"udlt {user_id} select {cid}",
        )
    btn.data_button("✖ Close", f"udlt {user_id} close")

    lines = [
        f"  ┟ <b>{title}</b> — <code>{cid}</code>  [{len(chat_dup_map.get(int(cid), {}))} dups]"
        for cid, title in chats_with_dups.items()
    ]
    lines[-1] = lines[-1].replace("┟", "┖")

    text = (
        "<b>User Delete Duplicates — Select Chat</b>\n"
        "────────────────\n"
        "⚙️ Uses <b>user session</b> for deletion.\n"
        "Choose a chat to delete its duplicate messages from:\n\n"
        + "\n".join(lines)
    )

    await send_message(message, text, btn.build_menu(1))


@new_task
async def udlt_cb(_, query):
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

        client = TgClient.user
        if client is None:
            return await query.answer(
                "User session not found! Set USER_SESSION_STRING in config.",
                show_alert=True,
            )

        user_scan = scan_data.get(owner_id, {})
        chat_dup_map = user_scan.get("chat_dup_map", {})
        scanned_chats = user_scan.get("scanned_chats", {})
        dup_map = chat_dup_map.get(chat_id, {})
        chat_title = scanned_chats.get(str(chat_id), str(chat_id))

        if not dup_map:
            return await query.answer("No duplicates for this chat!", show_alert=True)

        if await check_scan_running(owner_id):
            return await query.answer(
                "Task already running! Please wait for it to complete.",
                show_alert=True,
            )

        await query.answer(f"Starting user-session deletion for {chat_title}..")

        cancel_event = Event()
        bot_cache.setdefault("scan_cancel", {})[owner_id] = cancel_event
        mark_scan_start(owner_id)

        total = len(dup_map)
        deleted = 0
        failed = 0
        cancelled = False
        start_time = time()
        last_update = time()

        status_msg = await send_message(
            message,
            f"<b>User Delete Duplicates</b>\n"
            f"────────────────\n"
            f"┟ Chat     : <b>{chat_title}</b>\n"
            f"┟ Total    : <code>{total}</code> duplicate messages\n"
            f"┟ Session  : 👤 User Session\n"
            f"┖ Status   : Starting...",
            _udlt_cancel_button(owner_id),
        )

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
                LOGGER.warning(
                    f"UDlt Delete Failed | chat: {chat_id} | msg_id: {msg_id} | err: {err_str}"
                )
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
                        f"<b>User Delete Duplicates</b>\n"
                        f"────────────────\n"
                        f"┟ Chat      : <b>{chat_title}</b>\n"
                        f"┟ Session   : 👤 User Session\n"
                        f"┟ Progress  : <code>{idx}/{total}</code>\n"
                        f"┟ Deleted   : <code>{deleted}</code> ✓\n"
                        f"┟ Failed    : <code>{failed}</code> ✗\n"
                        f"┖ Elapsed   : <code>{get_readable_time(int(elapsed))}</code>",
                        _udlt_cancel_button(owner_id),
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
            if Config.DATABASE_URL:
                await database.update_scan_data(owner_id)
            await delete_message(status_msg)
            return await send_message(
                message,
                f"<b>Deletion Cancelled</b>\n"
                f"────────────────\n"
                f"┟ Chat      : <b>{chat_title}</b>\n"
                f"┟ Session   : 👤 User Session\n"
                f"┟ Deleted   : <code>{deleted}</code> messages\n"
                f"┟ Failed    : <code>{failed}</code>\n"
                f"┟ Remaining : <code>{total - deleted - failed}</code>\n"
                f"┖ Elapsed   : <code>{get_readable_time(int(elapsed))}</code>",
            )

        for fuid, _ in items:
            chat_dup_map[chat_id].pop(fuid, None)
            user_scan.get("total_dup_map", {}).pop(fuid, None)

        if Config.DATABASE_URL:
            await database.update_scan_data(owner_id)

        await delete_message(status_msg)
        await send_message(
            message,
            f"<b>Deletion Complete</b>\n"
            f"────────────────\n"
            f"┟ Chat      : <b>{chat_title}</b>\n"
            f"┟ Session   : 👤 User Session\n"
            f"┟ Total     : <code>{total}</code> duplicate messages\n"
            f"┟ Deleted   : <code>{deleted}</code> ✓\n"
            f"┟ Failed    : <code>{failed}</code> ✗\n"
            f"┖ Time      : <code>{get_readable_time(int(elapsed))}</code>",
        )
