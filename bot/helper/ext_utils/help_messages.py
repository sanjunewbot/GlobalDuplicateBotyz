# ruff: noqa: F403, F405

start = """<b>Gretting(s)</b>: 

Welcome 🤗"""

BASIC_HELP_DICT = {
    "main": start,
}

def get_bot_commands():
    static_commands = {
        "Start": "Start the bot",
        "Stats": "View bot resource and system statistics",
        "Help": "Show detailed help and command usage",
        "Ping": "Check bot response speed and latency",
        "Users": "List all authorized users and sudo members",
        "Authorize": "Authorize a user or chat to use the bot",
        "UnAuthorize": "Revoke authorization from a user or chat",
        "AddSudo": "Grant sudo privileges to a user",
        "RmSudo": "Remove sudo privileges from a user",
        "Broadcast": "Broadcast a message to all bot users",
        "Log": "Fetch the current bot log file",
        "BotSet": "Open bot settings and configuration panel",
        "Restart": "Restart the bot",
        "RestartSessions": "Restart Pyrogram user and bot sessions",
        "Check": "Scan a Telegram chat for duplicate files",
        "List": "View your scan stats and lifetime duplicate report",
        "Delete": "Delete duplicate messages from a scanned chat using bot session",
        "Udlt": "Delete duplicate messages from a scanned chat using user session",
        "Clear": "Clear all your stored scan data from the database",
    }

    return static_commands.copy()
    
BOT_COMMANDS = get_bot_commands()


def get_help_string():
    from ..telegram_helper.bot_commands import BotCommands

    help_lines = ["NOTE: Try each command without any argument to see more details."]

    commands = BotCommands.get_commands()

    for key, cmds in commands.items():
        cmd_attr = getattr(BotCommands, f"{key}Command", None)
        if not cmd_attr:
            continue

        if isinstance(cmd_attr, list):
            cmd_str = f"/{' or /'.join(cmd_attr)}"
        else:
            cmd_str = f"/{cmd_attr}"

        if key in BOT_COMMANDS:
            help_lines.append(f"{cmd_str}: {BOT_COMMANDS[key]}")

    return "\n".join(help_lines)


help_string = get_help_string()
