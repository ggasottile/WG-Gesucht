# WG-Gesucht Auto-Messenger Bot

Automatically finds new apartment/WG listings on WG-Gesucht.de in Munich, scores them, sends personalized messages, and emails you a daily recap.

## How It Works

```
Every 30 min (GitHub Actions):
  ┌─ Fetch up to 50 listings (WG rooms + studios, Munich, ≤€800)
  ├─ Score each listing (rent, location, size, WG composition)
  ├─ Score 65+  → generate message, schedule send (1-100 min delay)
  ├─ Score 50-64 → log as "worth a look"
  └─ Score <50   → silently ignored

Once daily at 8pm Munich time:
  └─ Email you a recap: what was messaged + what's worth a manual look
```

## Setup

### 1. Create a Gmail App Password

You need an App Password (not your regular Gmail password) to send emails:

1. Go to https://myaccount.google.com/apppasswords
2. You may need to enable 2-Factor Authentication first
3. Create an app password → name it "WG Bot"
4. Copy the 16-character password (e.g. `abcd efgh ijkl mnop`)

### 2. Create a public GitHub repo

```bash
# In the bot folder:
git init
git add .
git commit -m "Initial commit"
```

Create a **public** repo on GitHub, then:

```bash
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 3. Add GitHub Secrets

Go to repo → Settings → Secrets and variables → Actions → New repository secret.

| Secret | Value |
|--------|-------|
| `WG_EMAIL` | Your WG-Gesucht login email |
| `WG_PASSWORD` | Your WG-Gesucht password |
| `GMAIL_ADDRESS` | Your Gmail address (for sending the recap) |
| `GMAIL_APP_PASSWORD` | The 16-char App Password from step 1 |

Optional:

| Secret | Value |
|--------|-------|
| `OPENAI_API_KEY` | OpenAI key for personalized messages (uses template without it) |

### 4. Done

- The bot runs every 30 minutes automatically
- You get a recap email at 8pm Munich time every day
- Trigger manually anytime from the Actions tab

## Scoring

| Dimension | Max | Logic |
|-----------|-----|-------|
| Rent | /30 | €400-700 = max, linear drop to €800 |
| Location | /25 | Preferred district = max, other = 10 |
| Size | /25 | 15m²+ = max |
| WG size | /20 | Own apartment = 20, 2er WG = 15, 3er WG = 10, 4+ = 0 |

## Files

| File | Purpose |
|------|---------|
| `bot.py` | Main orchestrator (runs every 30 min) |
| `send_recap.py` | Sends the daily email recap |
| `config.py` | Preferences, scoring, personal info |
| `wg_client.py` | WG-Gesucht mobile API client |
| `scorer.py` | Listing scoring engine |
| `message_generator.py` | GPT / template message generation |
| `notifier.py` | Email recap builder + Gmail SMTP sender |
| `.github/workflows/run_bot.yml` | Bot cron (every 30 min) |
| `.github/workflows/daily_recap.yml` | Email recap cron (daily 8pm) |
