from time import time

from ... import (
    LOGGER,
    bot_cache,
    user_data,
)
from ...core.config_manager import Config
from ..telegram_helper.filters import CustomFilters
from ..telegram_helper.tg_utils import check_botpm, forcesub, verify_token
from .bot_utils import safe_int
from .status_utils import get_readable_time


async def check_scan_running(user_id):
    bot_cache.setdefault("active_scan", set())
    if user_id in bot_cache["active_scan"]:
        return True
    return False


def mark_scan_start(user_id):
    bot_cache.setdefault("active_scan", set())
    bot_cache["active_scan"].add(user_id)


def mark_scan_end(user_id):
    bot_cache.setdefault("active_scan", set())
    bot_cache["active_scan"].discard(user_id)


async def scan_interval_check(user_id):
    bot_cache.setdefault("scan_time_interval", {})
    if (time_interval := bot_cache["scan_time_interval"].get(user_id, False)) and (
        time() - time_interval
    ) < (UTI := Config.USER_TIME_INTERVAL):
        return UTI - (time() - time_interval)
    bot_cache["scan_time_interval"][user_id] = time()
    return None


async def pre_task_check(message):
    LOGGER.info("Running Pre Task Checks ...")
    msg = []
    button = None

    if await CustomFilters.sudo("", message):
        return msg, button

    user_id = (message.from_user or message.sender_chat).id

    if await check_scan_running(user_id):
        msg.append(
            "┠ <b>Scan Already Running</b>\n"
            "┠ <i>Your previous scan is still in progress.</i>\n"
            "┖ Please wait for it to complete before starting a new one."
        )
        return msg, button

    user_dict = user_data.get(user_id, {})

    if message.chat.type != message.chat.type.BOT:
        if ids := Config.FORCE_SUB_IDS:
            _msg, button = await forcesub(message, ids, button)
            if _msg:
                msg.append(_msg)
        if Config.BOT_PM or user_dict.get("BOT_PM"):
            _msg, button = await check_botpm(message, button)
            if _msg:
                msg.append(_msg)

    if hasattr(Config, "USER_TIME_INTERVAL") and (
        ut := await scan_interval_check(user_id)
    ):
        msg.append(
            f"┠ <b>Waiting Time</b> → {get_readable_time(ut)}\n"
            f"┖ <i>User Time Interval Restriction</i> → {get_readable_time(Config.USER_TIME_INTERVAL)}"
        )

    token_msg, button = await verify_token(user_id, button)
    if token_msg is not None:
        msg.append(token_msg)

    if msg:
        username = message.from_user.mention
        final_msg = f"⌬ <b>Task Checks :</b>\n│\n┟ <b>Name</b> → {username}\n┃\n"
        for m_part in msg:
            final_msg += f"{m_part}\n"
        if button is not None:
            button = button.build_menu(2)
        return final_msg, button

    return None, None
