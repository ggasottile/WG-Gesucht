"""
Email notification module.
Accumulates listing results throughout the day, then sends
a single daily recap email via Gmail SMTP.
"""

import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

# ─── Config ────────────────────────────────────────────────────────────
# Set these as GitHub Secrets / environment variables
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")       # your Gmail
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")  # Gmail App Password
RECAP_TO = os.environ.get("RECAP_TO", GMAIL_ADDRESS)      # recipient (defaults to yourself)

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
DAILY_LOG_FILE = os.path.join(BOT_DIR, "daily_results.json")


def log_result(offer: dict, detail: dict, score_result: dict,
               message_text: str, status: str = "scheduled"):
    """
    Append a listing result to today's daily log.
    Called by the bot for every listing above the notify threshold.
    """
    title = offer.get('offer_title', 'Unknown listing')
    offer_id = offer.get('offer_id', '')
    url = f"https://www.wg-gesucht.de/{offer_id}"

    entry = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'status': status,
        'title': title,
        'url': url,
        'rent': _get_rent(offer, detail),
        'size': _get_size(offer, detail),
        'district': _get_district(offer, detail),
        'score': score_result['total_score'],
        'breakdown': {k: f"{v['score']}/{v['max']} ({v['value']})"
                      for k, v in score_result['breakdown'].items()},
        'message': message_text
    }

    # Load existing daily log
    daily = _load_daily_log()
    daily.append(entry)
    _save_daily_log(daily)

    print(f"Logged result: {status} — {title} ({score_result['total_score']}/100)")


def log_status(text: str):
    """Log a simple status entry (e.g. message sent/failed confirmation)."""
    daily = _load_daily_log()
    daily.append({
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'status': 'info',
        'title': text,
        'url': '',
        'rent': '', 'size': '', 'district': '',
        'score': 0, 'breakdown': {}, 'message': ''
    })
    _save_daily_log(daily)


def send_daily_recap():
    """
    Send the accumulated daily results as an email and clear the log.
    Call this from a separate daily GitHub Actions job.
    """
    daily = _load_daily_log()

    if not daily:
        print("No results to send today.")
        return

    # Separate by status
    auto_sent = [e for e in daily if 'scheduled' in e['status'] or e['status'] == 'sent']
    notify_only = [e for e in daily if e['status'] == 'notify_only']
    info_items = [e for e in daily if e['status'] == 'info']

    # Build HTML email
    html = _build_email_html(auto_sent, notify_only, info_items)
    plain = _build_email_plain(auto_sent, notify_only, info_items)

    subject = f"🏠 WG-Gesucht Recap — {len(auto_sent)} messaged, {len(notify_only)} worth a look"

    _send_email(subject, html, plain)

    # Clear the daily log after sending
    _save_daily_log([])
    print(f"Recap sent: {len(auto_sent)} auto-sent, {len(notify_only)} notify-only")


def _build_email_html(auto_sent, notify_only, info_items):
    """Build a clean HTML email body."""
    lines = ['<div style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto;">']
    lines.append('<h2 style="color: #333;">WG-Gesucht Daily Recap</h2>')

    if auto_sent:
        lines.append(f'<h3 style="color: #2d7d46;">✅ Messages sent automatically ({len(auto_sent)})</h3>')
        for e in auto_sent:
            lines.append(_html_listing_card(e, '#e8f5e9'))

    if notify_only:
        lines.append(f'<h3 style="color: #e65100;">👀 Worth a look — apply manually ({len(notify_only)})</h3>')
        for e in notify_only:
            lines.append(_html_listing_card(e, '#fff3e0'))

    if info_items:
        lines.append('<h3 style="color: #666;">ℹ️ Status updates</h3>')
        for e in info_items:
            lines.append(f'<p style="color: #666; font-size: 13px;">{e["title"]}</p>')

    if not auto_sent and not notify_only:
        lines.append('<p style="color: #999;">No new matching listings found today.</p>')

    lines.append('</div>')
    return '\n'.join(lines)


def _html_listing_card(entry, bg_color):
    """Render one listing as an HTML card."""
    score = entry['score']
    breakdown = ' · '.join(f"{k}: {v}" for k, v in entry['breakdown'].items())

    msg_preview = entry['message'][:300]
    if len(entry['message']) > 300:
        msg_preview += '...'

    return f'''
    <div style="background: {bg_color}; border-radius: 8px; padding: 14px; margin: 10px 0;">
      <a href="{entry['url']}" style="font-size: 15px; font-weight: 600; color: #1a73e8; text-decoration: none;">
        {entry['title']}
      </a>
      <div style="margin-top: 6px; font-size: 13px; color: #555;">
        {entry['rent']} · {entry['size']} · {entry['district']}
      </div>
      <div style="margin-top: 4px; font-size: 13px; color: #777;">
        Score: <strong>{score}/100</strong> — {breakdown}
      </div>
      <div style="margin-top: 8px; font-size: 12px; color: #888; border-left: 3px solid #ccc; padding-left: 8px; white-space: pre-wrap;">
        {msg_preview}
      </div>
    </div>'''


def _build_email_plain(auto_sent, notify_only, info_items):
    """Build plain text fallback."""
    lines = ['WG-Gesucht Daily Recap', '=' * 40, '']

    if auto_sent:
        lines.append(f'--- MESSAGES SENT ({len(auto_sent)}) ---')
        for e in auto_sent:
            lines.append(f'\n{e["title"]}')
            lines.append(f'  {e["rent"]} | {e["size"]} | {e["district"]}')
            lines.append(f'  Score: {e["score"]}/100')
            lines.append(f'  Link: {e["url"]}')

    if notify_only:
        lines.append(f'\n--- WORTH A LOOK ({len(notify_only)}) ---')
        for e in notify_only:
            lines.append(f'\n{e["title"]}')
            lines.append(f'  {e["rent"]} | {e["size"]} | {e["district"]}')
            lines.append(f'  Score: {e["score"]}/100')
            lines.append(f'  Link: {e["url"]}')

    return '\n'.join(lines)


def _send_email(subject, html, plain):
    """Send email via Gmail SMTP."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("Gmail credentials not set. Skipping email.")
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f'WG Bot <{GMAIL_ADDRESS}>'
    msg['To'] = RECAP_TO

    msg.attach(MIMEText(plain, 'plain'))
    msg.attach(MIMEText(html, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=15) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print("Recap email sent successfully")
    except Exception as e:
        print(f"Email send error: {e}")


# ─── Helpers ───────────────────────────────────────────────────────────
def _load_daily_log():
    if os.path.exists(DAILY_LOG_FILE):
        try:
            with open(DAILY_LOG_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_daily_log(data):
    with open(DAILY_LOG_FILE, 'w') as f:
        json.dump(data, f, indent=2, default=str)


def _get_rent(offer, detail):
    for obj in [detail, offer]:
        if not obj:
            continue
        for key in ['total_costs', 'rent_costs', 'total_rent', 'rent']:
            if key in obj:
                try:
                    val = obj[key]
                    if isinstance(val, dict):
                        for sk in ['total', 'rent', 'amount']:
                            if sk in val:
                                return f"€{val[sk]}"
                    return f"€{val}"
                except:
                    continue
    return "unknown"


def _get_size(offer, detail):
    for obj in [detail, offer]:
        if not obj:
            continue
        for key in ['property_size', 'size', 'room_size', 'total_size']:
            if key in obj:
                try:
                    return f"{obj[key]}m²"
                except:
                    continue
    return "unknown"


def _get_district(offer, detail):
    for obj in [detail, offer]:
        if not obj:
            continue
        for key in ['district_custom', 'district', 'quarter', 'city_quarter']:
            if key in obj and obj[key]:
                return str(obj[key])
    return "Munich"
