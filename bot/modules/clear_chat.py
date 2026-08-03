from .. import LOGGER, scan_data
from ..core.config_manager import Config
from ..helper.ext_utils.bot_utils import new_task
from ..helper.ext_utils.db_handler import database
from ..helper.ext_utils.task_manager import pre_task_check, check_scan_running
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.message_utils import (
    delete_message,
    edit_message,
    send_message,
)


def _confirm_button(user_id, chat_id):
    btn = ButtonMaker()
    btn.data_button("✅ Yes, Clear It", f"clearchat {user_id} confirm {chat_id}")
    btn.data_button("✖ Cancel", f"clearchat {user_id} cancel {chat_id}")
    return btn.build_menu(2)


@new_task
async def clear_chat(_, message):
    user_id = message.from_user.id
    args = message.command

    error_msg, button = await pre_task_check(message)
    if error_msg:
        return await send_message(message, error_msg, button)

    if len(args) < 2:
        return await send_message(
            message,
            "<b>Invalid Usage</b>\n"
            "┖ <code>/clear -100xxxxxxxxxx</code>",
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

    user_scan = scan_data.get(user_id, {})
    scanned_chats = user_scan.get("scanned_chats", {})
    chat_dup_map = user_scan.get("chat_dup_map", {})
    chat_file_ids = user_scan.get("chat_file_ids", {})

    chat_title = scanned_chats.get(str(chat_id))
    has_data = (
        chat_title is not None
        or chat_dup_map.get(chat_id)
        or chat_file_ids.get(chat_id)
    )

    if not has_data:
        return await send_message(
            message,
            "<b>No Data Found</b>\n"
            f"┟ Chat ID : <code>{chat_id}</code>\n"
            "┖ This chat has no saved scan data to clear.",
        )

    if await check_scan_running(user_id):
        return await send_message(
            message,
            "<b>Task Already Running</b>\n"
            "┖ Wait for the current scan/deletion to finish before clearing.",
        )

    file_count = len(chat_file_ids.get(chat_id, set()))
    dup_count = len(chat_dup_map.get(chat_id, {}))

    await send_message(
        message,
        "<b>Clear Chat Data — Confirm</b>\n"
        "────────────────\n"
        f"┟ Chat          : <b>{chat_title or chat_id}</b>\n"
        f"┟ Chat ID       : <code>{chat_id}</code>\n"
        f"┟ Indexed Files : <code>{file_count}</code>\n"
        f"┟ Duplicates    : <code>{dup_count}</code>\n"
        "┖ This will permanently remove all saved data for this chat.\n\n"
        "Are you sure?",
        _confirm_button(user_id, chat_id),
    )


@new_task
async def clear_chat_cb(_, query):
    data = query.data.split()
    message = query.message
    user_id = query.from_user.id
    owner_id = int(data[1])
    action = data[2]
    chat_id = int(data[3])

    if user_id != owner_id and not await CustomFilters.sudo("", query):
        return await query.answer("Not Yours!", show_alert=True)

    if action == "cancel":
        await query.answer("Cancelled.")
        return await delete_message(message, message.reply_to_message)

    if action != "confirm":
        return

    user_scan = scan_data.get(owner_id)
    if not user_scan:
        await query.answer("No data found.", show_alert=True)
        return await delete_message(message, message.reply_to_message)

    scanned_chats = user_scan.get("scanned_chats", {})
    chat_dup_map = user_scan.setdefault("chat_dup_map", {})
    chat_file_ids = user_scan.setdefault("chat_file_ids", {})
    total_dup_map = user_scan.setdefault("total_dup_map", {})
    file_unique_ids = user_scan.setdefault("file_unique_ids", set())

    chat_title = scanned_chats.pop(str(chat_id), str(chat_id))
    this_chat_files = chat_file_ids.pop(chat_id, set())
    this_chat_dups = chat_dup_map.pop(chat_id, {})
    file_unique_ids.difference_update(this_chat_files)
    other_fuids = set()
    for fmap in chat_dup_map.values():
        other_fuids.update(fmap.keys())
    for fuid in this_chat_dups:
        if fuid not in other_fuids:
            total_dup_map.pop(fuid, None)

    if user_scan.get("last_scanned_chat_id") == chat_id:
        user_scan["last_dup_map"] = {}
        user_scan["last_scanned_chat_id"] = None

    if Config.DATABASE_URL:
        await database.update_scan_data(owner_id)

    LOGGER.info(
        f"Clear Chat | User: {owner_id} | Chat: {chat_title} ({chat_id}) | "
        f"Removed {len(this_chat_files)} files, {len(this_chat_dups)} dup entries"
    )

    await query.answer("Cleared!")
    await edit_message(
        message,
        "<b>Chat Data Cleared</b>\n"
        "────────────────\n"
        f"┟ Chat          : <b>{chat_title}</b>\n"
        f"┟ Chat ID       : <code>{chat_id}</code>\n"
        f"┟ Files Removed : <code>{len(this_chat_files)}</code>\n"
        f"┟ Dupes Removed : <code>{len(this_chat_dups)}</code>\n"
        "┖ Re-scanning this chat will now be treated as completely fresh.",
    )
