#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
구글 플레이 별점 변화 추적
────────────────────────────────────────────────────────────
매일 각 게임의 평균 별점을 읽어, 직전 기록과 비교해 변동을 메일로 보냅니다.
· 기록은 rating_history.json 파일에 저장되며, 다음 실행 때 '어제 값'으로 비교됩니다.
· 평일 아침 cron-job.org 등으로 실행하면 매일 변동 리포트를 받습니다.

필요 패키지:  pip install google-play-scraper
"""

import os
import sys
import json
import time
import smtplib
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr

from google_play_scraper import app as gp_app

# ────────────────────────────────────────────────────────────
# 1) 추적할 게임 목록  (필요하면 자유롭게 추가/삭제)
# ────────────────────────────────────────────────────────────
GAMES = [
    {"name": "컴투스프로야구2026",        "package": "com.com2us.probaseball3d.normal.freefull.google.global.android.common"},
    {"name": "컴투스프로야구V26",         "package": "com.com2us.futurecpb.android.google.global.normal"},
    {"name": "컴투스프로야구 for 매니저", "package": "com.com2us.kbomanager.normal2.freefull.google.global.android.common"},
    {"name": "MLB 9이닝스 라이벌 26",     "package": "com.com2us.futuremlb.android.google.global.normal"},
    {"name": "MLB 9이닝스 26",            "package": "com.com2us.ninepb3d.normal.freefull.google.global.android.common"},
    {"name": "서머너즈 워: 천공의 아레나","package": "com.com2us.smon.normal.freefull.google.kr.android.common"},
    {"name": "서머너즈 워: 러쉬",         "package": "com.com2us.legion.android.google.global.normal"},
    {"name": "서머너즈 워: 크로니클",     "package": "com.com2us.chronicles.android.google.kr.normal"},
    {"name": "아이모",                    "package": "com.com2us.imo.normal.freefull.google.global.android.common"},
    {"name": "낚시의 신",                 "package": "com.com2us.acefishing.normal.freefull.google.global.android.common"},
    {"name": "골프스타",                  "package": "com.com2us.golfstarworldtour.normal.freefull.google.global.android.common"},
    {"name": "미니게임천국",              "package": "com.com2us.minigame.android.google.global.normal"},
    {"name": "스타시드: 아스니아 트리거", "package": "com.com2us.starseedjp.android.google.jp.normal"},
    {"name": "몽키배틀",                  "package": "com.com2us.monkeybattlere.android.google.global.normal"},
]

# ────────────────────────────────────────────────────────────
# 2) 설정
# ────────────────────────────────────────────────────────────
HISTORY_FILE = "rating_history.json"  # 별점 기록 저장 파일
LANG, COUNTRY = "ko", "kr"
SLEEP_SEC = 1.5
ALERT_ONLY_ON_CHANGE = False  # True면 변동(하락/상승) 있을 때만 메일 발송

# 이메일 설정 (환경변수 권장 — 리뷰 시스템과 동일한 값 사용 가능)
SMTP_HOST = os.environ.get("SMTP_HOST") or "smtp.gmail.com"
SMTP_PORT = int(os.environ.get("SMTP_PORT") or 587)
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
MAIL_FROM = os.environ.get("MAIL_FROM") or SMTP_USER
MAIL_TO   = [a.strip() for a in os.environ.get("MAIL_TO", "").split(",") if a.strip()]
MAIL_NAME = os.environ.get("MAIL_NAME", "별점 추적 봇")

# 그래프 웹페이지 주소 (메일 하단 버튼에 사용). 비우면 버튼 미표시.
GRAPH_URL = "https://meiliem.github.io/rating-tracker/"


# ────────────────────────────────────────────────────────────
def load_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_history(hist):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)


def fetch_score(game):
    """평균 별점과 평가 수를 반환. (score, ratings, error)"""
    try:
        d = gp_app(game["package"], lang=LANG, country=COUNTRY)
        return d.get("score"), d.get("ratings"), None
    except Exception as e:
        return None, None, f"{type(e).__name__}: {e}"


def main():
    hist = load_history()
    today = datetime.now().strftime("%Y-%m-%d")
    rows, errors = [], []

    for i, g in enumerate(GAMES):
        score, ratings, err = fetch_score(g)
        if err:
            errors.append((g, err))
            print(f"[!] {g['name']}: {err}")
        else:
            entry = hist.get(g["package"], {"name": g["name"], "history": []})
            series = entry["history"]
            # 직전(오늘이 아닌 마지막) 값 = 비교 기준
            prev_score = None
            for date, sc in reversed(series):
                if date != today:
                    prev_score = sc
                    break
            delta = None if prev_score is None or score is None else round(score - prev_score, 2)
            rows.append({"game": g, "score": score, "ratings": ratings,
                         "prev": prev_score, "delta": delta})
            # 오늘 값 기록 (같은 날 재실행이면 덮어쓰고, 아니면 추가)
            if series and series[-1][0] == today:
                series[-1][1] = score
            else:
                series.append([today, score])
            entry["name"] = g["name"]
            entry["history"] = series
            hist[g["package"]] = entry
            arrow = "→" if not delta else ("▼" if delta < 0 else "▲")
            print(f"[+] {g['name']}: {score} ({arrow} {delta if delta is not None else '기준저장'})")
        if i < len(GAMES) - 1:
            time.sleep(SLEEP_SEC)

    save_history(hist)

    drops = [r for r in rows if r["delta"] is not None and r["delta"] < 0]
    if ALERT_ONLY_ON_CHANGE and not drops and not any(r["delta"] for r in rows):
        print("변동 없음 — 메일 발송 건너뜀")
        return

    subject, text, html = build_report(today, rows, drops, errors)
    send_email(subject, text, html)


# ────────────────────────────────────────────────────────────
def _fmt(v):
    return "—" if v is None else f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def build_report(today, rows, drops, errors):
    rose = [r for r in rows if r["delta"] is not None and r["delta"] > 0]
    same = [r for r in rows if r["delta"] == 0]
    first = [r for r in rows if r["delta"] is None]

    # 정렬: 하락(큰 폭 우선) → 상승 → 변화없음 → 기준저장
    def order(r):
        d = r["delta"]
        if d is None:   return (3, 0)
        if d < 0:       return (0, d)      # 더 많이 떨어진 게 위
        if d > 0:       return (1, -d)
        return (2, 0)
    rows_sorted = sorted(rows, key=order)

    # 텍스트
    lines = [f"[별점 추적] {today}",
             f"하락 {len(drops)}개 · 상승 {len(rose)}개 · 변화없음 {len(same)}개 · 점검 {len(rows)}개", ""]
    for r in rows_sorted:
        g, d = r["game"], r["delta"]
        arrow = "기준저장" if d is None else ("▼" if d < 0 else "▲" if d > 0 else "−")
        prev = _fmt(r["prev"]); cur = _fmt(r["score"])
        ds = "" if d is None else f" ({d:+.2f})"
        lines.append(f" {arrow} {g['name']}: {prev} → {cur}{ds}")
    if errors:
        lines.append("")
        lines.append(f"⚠️ 수집 실패 {len(errors)}개: " + ", ".join(g["name"] for g, _ in errors))
    if GRAPH_URL:
        lines.append("")
        lines.append("📈 별점 추이 그래프는 메일 하단의 '그래프로 추이 보기' 버튼에서 확인하세요.")
    text = "\n".join(lines)

    # HTML
    base = "font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#222;line-height:1.5;"
    h = [f"<div style=\"{base}max-width:620px;\">"]
    h.append(f"<div style='font-size:17px;font-weight:600;'>📊 별점 추적 — {today}</div>")
    h.append(f"<div style='font-size:13px;color:#666;margin-top:3px;'>"
             f"<b style='color:#c0392b;'>하락 {len(drops)}</b> · "
             f"<b style='color:#185FA5;'>상승 {len(rose)}</b> · 변화없음 {len(same)} · 점검 {len(rows)}개</div>")
    h.append("<table style='border-collapse:collapse;width:100%;font-size:13px;margin-top:14px;'>")
    h.append("<tr style='background:#f4f4f4;'>"
             "<th style='text-align:left;padding:7px 8px;'>게임</th>"
             "<th style='text-align:right;padding:7px 8px;'>어제</th>"
             "<th style='text-align:right;padding:7px 8px;'>오늘</th>"
             "<th style='text-align:right;padding:7px 8px;'>변동</th></tr>")
    for r in rows_sorted:
        g, d = r["game"], r["delta"]
        if d is None:
            badge, color = "기준 저장", "#999"
        elif d < 0:
            badge, color = f"▼ {d:+.2f}", "#c0392b"
        elif d > 0:
            badge, color = f"▲ {d:+.2f}", "#185FA5"
        else:
            badge, color = "−", "#bbb"
        h.append("<tr style='border-bottom:1px solid #eee;'>"
                 f"<td style='padding:7px 8px;'>{g['name']}</td>"
                 f"<td style='padding:7px 8px;text-align:right;color:#888;'>{_fmt(r['prev'])}</td>"
                 f"<td style='padding:7px 8px;text-align:right;font-weight:600;'>{_fmt(r['score'])}</td>"
                 f"<td style='padding:7px 8px;text-align:right;color:{color};font-weight:600;white-space:nowrap;'>{badge}</td></tr>")
    h.append("</table>")
    if GRAPH_URL:
        h.append(f"<div style='margin-top:14px;'><a href='{GRAPH_URL}' "
                 "style='display:inline-block;font-size:13px;color:#185FA5;text-decoration:none;"
                 "border:1px solid #cdddef;border-radius:7px;padding:8px 14px;'>📈 그래프로 추이 보기 →</a></div>")
    if errors:
        h.append("<div style='background:#FAEEDA;border-radius:8px;padding:10px 13px;margin-top:12px;'>"
                 f"<span style='font-size:12.5px;color:#854F0B;'>⚠️ 수집 실패 {len(errors)}개 — "
                 + ", ".join(g["name"] for g, _ in errors) + "</span></div>")
    h.append("</div>")
    html = "\n".join(h)

    n = len(drops)
    subject = f"[별점 추적] 하락 {n}개 — {today}" if n else f"[별점 추적] 변동 요약 — {today}"
    return subject, text, html


def send_email(subject, text_body, html_body):
    if not (SMTP_USER and SMTP_PASS and MAIL_TO):
        print("[경고] 메일 설정이 없어 발송 건너뜀.\n--- 미리보기 ---")
        print("Subject:", subject); print(text_body)
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((MAIL_NAME, MAIL_FROM))
    msg["To"] = ", ".join(MAIL_TO)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls(); s.login(SMTP_USER, SMTP_PASS); s.send_message(msg)
    print(f"[완료] 메일 발송 → {', '.join(MAIL_TO)}")


if __name__ == "__main__":
    main()
