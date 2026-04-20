"""
Configuration for WG-Gesucht Auto-Messenger Bot

INSTRUCTIONS:
1. Set your credentials as environment variables or GitHub Secrets
2. Adjust search preferences and scoring weights as needed
3. Edit the PERSONAL_INFO to match your profile
"""

import os

# ─── WG-Gesucht Credentials ───────────────────────────────────────────
# Set these as GitHub Secrets (or environment variables for local use)
WG_EMAIL = os.environ.get("WG_EMAIL", "")
WG_PASSWORD = os.environ.get("WG_PASSWORD", "")

# ─── Search Parameters ─────────────────────────────────────────────────
CITY_ID = "90"           # Munich = 90
CITY_NAME = "München"

# Categories: 0=WG-Zimmer, 1=1-Zimmer-Wohnung, 2=Wohnung, 3=Haus
CATEGORIES = "0,1"       # WG rooms + 1-room apartments

MAX_RENT = "800"         # Maximum warm rent in €
MIN_SIZE = "10"          # Minimum room/apartment size in m²
MAX_LISTINGS = 50        # Max listings to fetch per run (API returns 25/page)

# ─── Scoring Preferences ──────────────────────────────────────────────
# Each listing gets a score from 0-100. Only listings above the
# threshold get an automatic message.

# Score tiers:
#   65+  → auto-send a personalized message
#   50-64 → Slack notification only (no message sent)
#   <50  → ignored entirely
SCORE_AUTO_SEND = 65
SCORE_NOTIFY_ONLY = 50

# Preferred districts in Munich (lowercase). Listings here get bonus points.
PREFERRED_DISTRICTS = [
    "maxvorstadt", "schwabing", "schwabing-west", "schwanthalerhöhe",
    "ludwigsvorstadt", "isarvorstadt", "au-haidhausen", "haidhausen",
    "sendling", "neuhausen", "nymphenburg", "lehel", "altstadt",
    "glockenbachviertel", "giesing", "untergiesing",
    "berg am laim", "bogenhausen", "trudering",
]

# Maximum number of roommates for WG (you said 1 roommate preferred)
MAX_ROOMMATES = 2  # Total people in WG including you

# Ideal rent range (listings in this range get max rent score)
IDEAL_RENT_MIN = 400
IDEAL_RENT_MAX = 700

# Ideal size range in m²
IDEAL_SIZE_MIN = 14
IDEAL_SIZE_MAX = 30

# ─── Messaging ─────────────────────────────────────────────────────────
# Random delay range (in minutes) before sending a message after
# discovering a new listing. This helps avoid detection.
MESSAGE_DELAY_MIN = 1
MESSAGE_DELAY_MAX = 100

# Your personal info used to generate messages
PERSONAL_INFO = """
Name: Gianluigi
Age: 24
Profession: Business consultant
German level: B1 (currently taking classes, improving every week)
Personality: Extroverted but also enjoy quiet evenings. I usually go to bed between 11pm and midnight during the week, and between midnight and 1am on weekends.
Cleaning: I have a weekly routine to deep-clean my room and all shared spaces.
Cooking: I love cooking and spend quite some time in the kitchen — happy to coordinate kitchen times if shared.
General: I'm an agreeable, easygoing person. I get along very easily with people my age. I'm looking for a comfortable place where I can feel at home.
Move-in flexibility: I'm flexible on the move-in date — could be any month.
"""

# ─── Paths ─────────────────────────────────────────────────────────────
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_FILE = os.path.join(BOT_DIR, "seen_offers.json")
PENDING_FILE = os.path.join(BOT_DIR, "pending_messages.json")
SESSION_FILE = os.path.join(BOT_DIR, "session.json")
LOG_FILE = os.path.join(BOT_DIR, "bot.log")
