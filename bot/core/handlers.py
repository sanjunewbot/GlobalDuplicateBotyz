from pyrogram.filters import command, regex
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import BotCommand

from ..core.config_manager import Config
from ..helper.ext_utils.help_messages import BOT_COMMANDS
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.filters import CustomFilters
from ..modules import *
from .tg_client import TgClient


def add_handlers():
    TgClient.bot.add_handler(
    MessageHandler(
        user_delete_duplicates,
        filters=command(BotCommands.UdltCommand, case_sensitive=True)
        & CustomFilters.sudo,
    )
    )
    TgClient.bot.add_handler(
    CallbackQueryHandler(
        udlt_cb,
        filters=regex("^udlt"),
    )
    )
    TgClient.bot.add_handler(
    MessageHandler(
        clear_chat,
        filters=command(BotCommands.ClearCommand, case_sensitive=True)
        & CustomFilters.sudo,
    )
    )
    TgClient.bot.add_handler(
    CallbackQueryHandler(
        clear_chat_cb,
        filters=regex("^clearchat"),
    )
    )
    TgClient.bot.add_handler(
    MessageHandler(
        delete_duplicates,
        filters=command(BotCommands.DeleteCommand, case_sensitive=True)
        & CustomFilters.sudo,
    )
    )
    TgClient.bot.add_handler(
    CallbackQueryHandler(
        deldups_cb,
        filters=regex("^deldups"),
    )
    )
    TgClient.bot.add_handler(
        MessageHandler(
            check_duplicates,
            filters=command(BotCommands.CheckCommand, case_sensitive=True)
            & CustomFilters.sudo,
        )
    )
    TgClient.bot.add_handler(
        CallbackQueryHandler(
            scan_cancel_cb,
            filters=regex("^scancancel"),
        )
    )
    TgClient.bot.add_handler(
        CallbackQueryHandler(
            dup_list_cb,
            filters=regex("^duplist"),
        )
    )
    TgClient.bot.add_handler(
        MessageHandler(
            scan_list,
            filters=command(BotCommands.ListCommand, case_sensitive=True)
            & CustomFilters.sudo,
        )
    )
    TgClient.bot.add_handler(
        CallbackQueryHandler(
            dupmang_cb,
            filters=regex("^dupmang"),
        )
    )
    TgClient.bot.add_handler(
        MessageHandler(
            send_bot_settings,
            filters=command(BotCommands.BotSetCommand, case_sensitive=True)
            & CustomFilters.sudo,
        )
    )
    TgClient.bot.add_handler(
        CallbackQueryHandler(
            edit_bot_settings, filters=regex("^botset") & CustomFilters.sudo
        )
    )
    TgClient.bot.add_handler(
        MessageHandler(
            authorize,
            filters=command(BotCommands.AuthorizeCommand, case_sensitive=True)
            & CustomFilters.sudo,
        )
    )
    TgClient.bot.add_handler(
        MessageHandler(
            unauthorize,
            filters=command(BotCommands.UnAuthorizeCommand, case_sensitive=True)
            & CustomFilters.sudo,
        )
    )
    TgClient.bot.add_handler(
        MessageHandler(
            add_sudo,
            filters=command(BotCommands.AddSudoCommand, case_sensitive=True)
            & CustomFilters.sudo,
        )
    )
    TgClient.bot.add_handler(
        MessageHandler(
            remove_sudo,
            filters=command(BotCommands.RmSudoCommand, case_sensitive=True)
            & CustomFilters.sudo,
        )
    )
    TgClient.bot.add_handler(
        MessageHandler(
            broadcast,
            filters=command(BotCommands.BroadcastCommand, case_sensitive=True)
            & CustomFilters.sudo,
        )
    )
    TgClient.bot.add_handler(
        MessageHandler(
            start,
            filters=command(BotCommands.StartCommand, case_sensitive=True),
        )
    )
    TgClient.bot.add_handler(
        MessageHandler(
            log,
            filters=command(BotCommands.LogCommand, case_sensitive=True)
            & CustomFilters.sudo,
        )
    )
    TgClient.bot.add_handler(
        MessageHandler(
            restart_bot,
            filters=command(BotCommands.RestartCommand, case_sensitive=True)
            & CustomFilters.sudo,
        )
    )
    TgClient.bot.add_handler(
        CallbackQueryHandler(
            confirm_restart,
            filters=regex("^botrestart") & CustomFilters.sudo,
        )
    )
    TgClient.bot.add_handler(
        MessageHandler(
            restart_sessions,
            filters=command(BotCommands.RestartSessionsCommand, case_sensitive=True)
            & CustomFilters.sudo,
        )
    )
    TgClient.bot.add_handler(
        MessageHandler(
            ping,
            filters=command(BotCommands.PingCommand, case_sensitive=True)
            & CustomFilters.authorized,
        )
    )
    TgClient.bot.add_handler(
        MessageHandler(
            bot_help,
            filters=command(BotCommands.HelpCommand, case_sensitive=True)
            & CustomFilters.authorized,
        )
    )
    TgClient.bot.add_handler(
        MessageHandler(
            bot_stats,
            filters=command(BotCommands.StatsCommand, case_sensitive=True)
            & CustomFilters.authorized,
        )
    )
    TgClient.bot.add_handler(
        CallbackQueryHandler(stats_pages, filters=regex("^stats"))
    )
    TgClient.bot.add_handler(
        CallbackQueryHandler(log_cb, filters=regex("^log"))
    )
    TgClient.bot.add_handler(
        CallbackQueryHandler(start_cb, filters=regex("^start"))
    )

    if Config.SET_COMMANDS:
        global BOT_COMMANDS

        def insert_at(d, k, v, i):
            return dict(list(d.items())[:i] + [(k, v)] + list(d.items())[i:])

        TgClient.bot.set_bot_commands(
            [
                BotCommand(
                    cmds[0] if isinstance(cmds, list) else cmds,
                    description,
                )
                for cmd, description in BOT_COMMANDS.items()
                for cmds in [getattr(BotCommands, f"{cmd}Command", None)]
                if cmds is not None
            ]
        )
