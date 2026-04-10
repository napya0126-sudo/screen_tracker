import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "activity_log.jsonl"
POLL_SECONDS = 5
IDLE_THRESHOLD_SECONDS = 600
MEET_TITLE_PATTERN = re.compile(r"(meet\.google\.com|google meet)", re.IGNORECASE)
ZOOM_TITLE_PATTERN = re.compile(r"(zoom|meeting)", re.IGNORECASE)


def run_command(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


BROWSER_APPS = {"Google Chrome", "Dia"}


def get_active_tab_url(front_app: str) -> str:
    if front_app not in BROWSER_APPS:
        return ""
    script = f"""
tell application "{front_app}"
    try
        get URL of active tab of front window
    on error
        return ""
    end try
end tell
"""
    return run_command(["osascript", "-e", script])


def get_frontmost_window() -> tuple[str, str]:
    script = """
tell application "System Events"
    set frontApp to name of first application process whose frontmost is true
    set frontTitle to ""
    try
        tell process frontApp
            set frontTitle to name of front window
        end tell
    end try
    return frontApp & "||" & frontTitle
end tell
"""
    output = run_command(["osascript", "-e", script])
    if "||" in output:
        app_name, window_title = output.split("||", 1)
        return app_name.strip(), window_title.strip()
    return "Unknown", ""


def get_idle_seconds() -> int:
    output = run_command(["ioreg", "-c", "IOHIDSystem"])
    match = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', output)
    if not match:
        return 0
    idle_nanos = int(match.group(1))
    return idle_nanos // 1_000_000_000


def get_status(idle_seconds: int) -> str:
    if idle_seconds >= IDLE_THRESHOLD_SECONDS:
        return "Idle"
    return "Active"


def get_running_process_names() -> set[str]:
    output = run_command(["ps", "-axo", "comm="])
    if not output:
        return set()
    names: set[str] = set()
    for line in output.splitlines():
        name = line.strip().split("/")[-1]
        if name:
            names.add(name)
    return names


def detect_meeting_context(front_app: str, window_title: str, status: str) -> dict:
    """
    Meeting heuristics:
    - Teams is intentionally excluded from meeting detection.
    - Zoom can be detected even in background by process name.
    - Google Meet is detected from front tab title.
    """
    process_names = get_running_process_names()
    running_meeting_apps: list[str] = []

    zoom_running = "zoom.us" in process_names
    if zoom_running:
        running_meeting_apps.append("Zoom")

    front_is_zoom = front_app == "zoom.us" and bool(ZOOM_TITLE_PATTERN.search(window_title))
    front_is_google_meet = front_app in {"Google Chrome", "Dia", "Safari"} and bool(
        MEET_TITLE_PATTERN.search(window_title)
    )

    meeting_status = "none"
    meeting_tool = ""
    confidence = "low"
    reasons: list[str] = []

    if status == "Idle":
        confidence = "none"
        reasons.append("idle")
    else:
        if front_is_zoom:
            meeting_status = "in_meeting"
            meeting_tool = "Zoom"
            confidence = "high"
            reasons.append("zoom_front_window")
        elif front_is_google_meet:
            meeting_status = "in_meeting"
            meeting_tool = "Google Meet"
            confidence = "high"
            reasons.append("meet_front_tab")
        elif zoom_running:
            meeting_status = "meeting_candidate"
            meeting_tool = "Zoom"
            confidence = "medium"
            reasons.append("zoom_process_running")

    return {
        "meeting_status": meeting_status,
        "meeting_tool": meeting_tool,
        "meeting_confidence": confidence,
        "meeting_reasons": reasons,
        "running_meeting_apps": running_meeting_apps,
    }


def make_record() -> dict:
    app_name, window_title = get_frontmost_window()
    idle_seconds = get_idle_seconds()
    status = get_status(idle_seconds)
    active_tab_url = get_active_tab_url(app_name)
    meeting_context = detect_meeting_context(app_name, window_title, status)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "application_name": app_name,
        "window_title": window_title,
        "active_tab_url": active_tab_url,
        "status": status,
        "analysis_excluded": app_name == "Python",
        **meeting_context,
    }


def append_record(record: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    print(f"Start tracking: interval={POLL_SECONDS}s idle={IDLE_THRESHOLD_SECONDS}s")
    print(f"Log file: {LOG_FILE}")
    while True:
        record = make_record()
        append_record(record)
        print(
            f"[{record['timestamp']}] {record['status']} | "
            f"{record['application_name']} | {record['window_title']}"
        )
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
