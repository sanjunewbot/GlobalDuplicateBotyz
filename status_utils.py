from re import findall

SIZE_UNITS = ["B", "KB", "MB", "GB", "TB", "PB"]

def get_readable_file_size(size_in_bytes):
    if not size_in_bytes:
        return "0B"

    index = 0
    while size_in_bytes >= 1024 and index < len(SIZE_UNITS) - 1:
        size_in_bytes /= 1024
        index += 1

    return f"{size_in_bytes:.2f}{SIZE_UNITS[index]}"


def get_readable_time(seconds: int):
    periods = [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]
    result = ""
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            result += f"{int(period_value)}{period_name}"
    return result


def get_raw_time(time_str: str) -> int:
    time_units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    return sum(
        int(value) * time_units[unit]
        for value, unit in findall(r"(\d+)([dhms])", time_str)
    )


def time_to_seconds(time_duration):
    try:
        parts = time_duration.split(":")
        if len(parts) == 3:
            hours, minutes, seconds = map(float, parts)
        elif len(parts) == 2:
            hours = 0
            minutes, seconds = map(float, parts)
        elif len(parts) == 1:
            hours = 0
            minutes = 0
            seconds = float(parts[0])
        else:
            return 0
        return hours * 3600 + minutes * 60 + seconds
    except Exception:
        return 0

def get_progress_bar_string(pct):
    pct = float(str(pct).strip("%"))
    p = min(max(pct, 0), 100)
    cFull = int(p // 8)
    p_str = "⬤" * cFull
    p_str += "□" * (12 - cFull)
    return f"[{p_str}]"

def get_scan_status_msg(chat_title, chat_id, total, new_ids, dup_entries, cross_dup, existing_count, elapsed):
    total_dupes = dup_entries + cross_dup
    speed_est = f"{total / elapsed:.0f} msg/s" if elapsed > 0 else "..."
    return (
        "<b>Duplicate Scanner — Running</b>\n"
        "────────────────\n"
        f"┏ Chat          : <b>{chat_title}</b>\n"
        f"┃ Chat ID       : <code>{chat_id}</code>\n"
        "┃\n"
        f"┃ Scanned       : <code>{total}</code> messages\n"
        f"┃ Speed         : <code>{speed_est}</code>\n"
        f"┃ Elapsed       : <code>{get_readable_time(int(elapsed))}</code>\n"
        "┃\n"
        f"┃ Pre-Indexed   : <code>{existing_count}</code> files\n"
        f"┃ New Found     : <code>{len(new_ids)}</code> files\n"
        "┃\n"
        f"┃ Same-Chat     : <code>{dup_entries}</code> dupes\n"
        f"┃ Cross-Chat    : <code>{cross_dup}</code> dupes\n"
        f"┗ Total Dupes   : <code>{total_dupes}</code>"
        "\n────────────────"
    )
      
