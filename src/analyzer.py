#!/usr/bin/env python3
"""作業時間アナライザ

使い方:
  python3 src/analyzer.py           # 今日のサマリ
  python3 src/analyzer.py --date 2026-04-08   # 指定日
  python3 src/analyzer.py --week    # 今週（月曜〜今日）
"""

import argparse
import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

LOG_FILE = Path("logs/activity_log.jsonl")
POLL_SECONDS = 5

# --- URL 分類ルール ---
# staging を先にチェックして本番パターンへの誤マッチを防ぐ
_VETTY_STG = re.compile(
    r"https?://(?:staging\.vetty\.clinic|[a-z0-9]+\.stg-cs\.vetty\.clinic)"
)
_VETTY_PROD = re.compile(r"https?://([a-z0-9]+)\.vetty\.clinic")

# (パターン, カテゴリ) の順序付きリスト。上から順にマッチを試みる
URL_RULES: list[tuple[re.Pattern, str]] = [
    (_VETTY_STG, "開発確認"),
    (re.compile(r"https?://app\.slack\.com"), "チャット対応"),
    (re.compile(r"https?://(?:www\.)?notion\.so"), "タスク管理"),
    (re.compile(r"https?://linear\.app"), "タスク管理"),
    (re.compile(r"https?://mail\.google\.com"), "メール"),
    (re.compile(r"https?://(?:meet\.google\.com|zoom\.us)"), "会議"),
]

# URL が取れないアプリ（ネイティブアプリなど）の分類
APP_RULES: dict[str, str] = {
    "Slack": "チャット対応",
    "Microsoft Teams": "チャット対応",
    "Notion": "タスク管理",
    "zoom.us": "会議",
    "FaceTime": "会議",
    "Mail": "メール",
}


# --- 分類ロジック ---

def classify(record: dict) -> tuple[str, str]:
    """(カテゴリ, 病院ID) を返す。病院ID は本番対応のみ設定される。"""
    if record.get("meeting_status") == "in_meeting":
        return "会議", ""

    url: str = record.get("active_tab_url", "")
    app: str = record.get("application_name", "")

    if url:
        for pattern, category in URL_RULES:
            if pattern.search(url):
                return category, ""
        m = _VETTY_PROD.search(url)
        if m:
            return "本番対応", m.group(1)

    return APP_RULES.get(app, "その他"), ""


# --- ログ読み込み ---

def load_records(start_date: date, end_date: date) -> list[dict]:
    """start_date 以上 end_date 未満（ローカル時刻）のレコードを返す。"""
    if not LOG_FILE.exists():
        return []
    records: list[dict] = []
    with LOG_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts_local = datetime.fromisoformat(r["timestamp"]).astimezone()
            if start_date <= ts_local.date() < end_date:
                records.append(r)
    return records


# --- 集計 ---

def aggregate(records: list[dict]) -> dict:
    cat_secs: defaultdict[str, int] = defaultdict(int)
    hospital_secs: defaultdict[str, int] = defaultdict(int)
    total_active = 0
    total_idle = 0

    for r in records:
        if r.get("analysis_excluded"):
            continue
        if r.get("status") == "Idle":
            total_idle += POLL_SECONDS
            continue
        total_active += POLL_SECONDS
        cat, hospital_id = classify(r)
        cat_secs[cat] += POLL_SECONDS
        if cat == "本番対応" and hospital_id:
            hospital_secs[hospital_id] += POLL_SECONDS

    return {
        "cat_secs": dict(cat_secs),
        "hospital_secs": dict(hospital_secs),
        "total_active": total_active,
        "total_idle": total_idle,
    }


# --- フォーマット ---

def fmt_time(seconds: int) -> str:
    h, m = divmod(seconds // 60, 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"


def print_summary(data: dict) -> None:
    cat_secs = data["cat_secs"]
    hospital_secs = data["hospital_secs"]
    total_active = data["total_active"]
    total_idle = data["total_idle"]

    if total_active == 0:
        print("  アクティブな記録なし")
        return

    print("\nカテゴリ別")
    for cat, secs in sorted(cat_secs.items(), key=lambda x: -x[1]):
        pct = secs * 100 // total_active
        bar = "█" * (pct // 5)
        print(f"  {cat:<16} {fmt_time(secs):>8}  {pct:>3}%  {bar}")

    if hospital_secs:
        print("\n本番対応 - 病院別")
        for hid, secs in sorted(hospital_secs.items(), key=lambda x: -x[1]):
            print(f"  {hid:<24} {fmt_time(secs):>8}")

    print(f"\n合計アクティブ: {fmt_time(total_active)}")
    print(f"アイドル:       {fmt_time(total_idle)}")


def print_weekly(records: list[dict], start_date: date, today: date) -> None:
    """週次レポート: 日別サマリ + 週合計を出力する。"""
    by_day: defaultdict[date, list[dict]] = defaultdict(list)
    for r in records:
        d = datetime.fromisoformat(r["timestamp"]).astimezone().date()
        by_day[d].append(r)

    weekly_cat: defaultdict[str, int] = defaultdict(int)
    weekly_hospital: defaultdict[str, int] = defaultdict(int)
    weekly_active = 0
    weekly_idle = 0

    current = start_date
    while current <= today:
        day_records = by_day.get(current, [])
        if day_records:
            data = aggregate(day_records)
            print(f"\n--- {current.strftime('%m/%d (%a)')} ---")
            print_summary(data)
            for cat, secs in data["cat_secs"].items():
                weekly_cat[cat] += secs
            for hid, secs in data["hospital_secs"].items():
                weekly_hospital[hid] += secs
            weekly_active += data["total_active"]
            weekly_idle += data["total_idle"]
        current += timedelta(days=1)

    print("\n" + "=" * 40)
    print("週合計")
    print_summary({
        "cat_secs": dict(weekly_cat),
        "hospital_secs": dict(weekly_hospital),
        "total_active": weekly_active,
        "total_idle": weekly_idle,
    })


# --- エントリーポイント ---

def main() -> None:
    parser = argparse.ArgumentParser(description="作業時間アナライザ")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--date", metavar="YYYY-MM-DD", help="指定日（デフォルト: 今日）")
    group.add_argument("--week", action="store_true", help="今週（月曜〜今日）")
    args = parser.parse_args()

    today = date.today()

    if args.week:
        start_date = today - timedelta(days=today.weekday())
        label = f"{start_date} 〜 {today}（今週）"
        print(f"=== 作業時間サマリ {label} ===")
        records = load_records(start_date, today + timedelta(days=1))
        print(f"総レコード数: {len(records)}")
        print_weekly(records, start_date, today)
    else:
        if args.date:
            target = date.fromisoformat(args.date)
        else:
            target = today
        label = f"{target}（{'今日' if target == today else target.strftime('%A')}）"
        print(f"=== 作業時間サマリ {label} ===")
        records = load_records(target, target + timedelta(days=1))
        print(f"レコード数: {len(records)}")
        print_summary(aggregate(records))


if __name__ == "__main__":
    main()
