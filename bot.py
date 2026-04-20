#!/usr/bin/env python3
"""
WG-Gesucht Auto-Messenger Bot — Main Orchestrator

This script:
1. Logs into WG-Gesucht (or reuses saved session)
2. Fetches new listings matching your criteria
3. Scores each listing against your preferences
4. Generates a personalized message for high-scoring listings
5. Schedules the message with a random delay (1-100 min)
6. Sends a Slack notification for each match
7. Processes any pending delayed messages that are due

Run this every 15 minutes via cron.
"""

import json
import os
import sys
import time
import random
import logging
from datetime import datetime, timezone

# Add bot directory to path
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BOT_DIR)

import config
from wg_client import WgGesuchtClient
from scorer import score_listing, format_score_summary
from message_generator import generate_message
from notifier import log_result, log_status


# ─── Logging Setup ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("wg-bot")


# ─── Persistence Helpers ───────────────────────────────────────────────
def load_json(path, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return default
    return default


def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)


# ─── Session Management ───────────────────────────────────────────────
def get_client() -> WgGesuchtClient:
    """Get an authenticated WG-Gesucht client."""
    client = WgGesuchtClient()
    
    # Try to reuse saved session
    session = load_json(config.SESSION_FILE)
    if session and 'userId' in session:
        client.import_account(session)
        log.info(f"Loaded saved session for user {session['userId']}")
        return client
    
    # Fresh login
    log.info("Logging in to WG-Gesucht...")
    if client.login(config.WG_EMAIL, config.WG_PASSWORD):
        save_json(config.SESSION_FILE, client.export_account())
        log.info("Login successful, session saved.")
        return client
    else:
        log.error("Login failed! Check your credentials in config.py")
        return None


# ─── Fetch New Listings ───────────────────────────────────────────────
def fetch_new_listings(client: WgGesuchtClient) -> list:
    """Fetch listings (up to MAX_LISTINGS) and filter to only new (unseen) ones."""
    seen = load_json(config.SEEN_FILE, default={})

    log.info(f"Fetching listings: Munich, categories={config.CATEGORIES}, "
             f"max rent=€{config.MAX_RENT}, limit={config.MAX_LISTINGS}")

    all_offers = []
    page = 1
    per_page = 25  # API returns 25 per page

    while len(all_offers) < config.MAX_LISTINGS:
        offers = client.offers(
            city_id=config.CITY_ID,
            categories=config.CATEGORIES,
            max_rent=config.MAX_RENT,
            min_size=config.MIN_SIZE,
            page=str(page)
        )

        if not offers:
            break

        all_offers.extend(offers)
        log.info(f"  Page {page}: {len(offers)} listings")

        if len(offers) < per_page:
            break  # Last page

        page += 1
        time.sleep(random.uniform(1.5, 3.0))

    # Trim to the configured limit
    all_offers = all_offers[:config.MAX_LISTINGS]
    log.info(f"Fetched {len(all_offers)} total listings from API")

    # Filter to new listings
    new_offers = []
    for offer in all_offers:
        offer_id = str(offer.get('offer_id', ''))
        if offer_id and offer_id not in seen:
            new_offers.append(offer)
            seen[offer_id] = {
                'first_seen': datetime.now(timezone.utc).isoformat(),
                'title': offer.get('offer_title', ''),
            }

    save_json(config.SEEN_FILE, seen)
    log.info(f"Found {len(new_offers)} new listings (total seen: {len(seen)})")

    return new_offers


# ─── Process a Single Listing ─────────────────────────────────────────
def process_listing(client: WgGesuchtClient, offer: dict) -> dict:
    """
    Process a single listing: get details, score it, and optionally
    generate a message and schedule it.
    """
    offer_id = str(offer.get('offer_id', ''))
    title = offer.get('offer_title', 'Unknown')
    
    log.info(f"Processing: {title} (ID: {offer_id})")
    
    # Get full details
    detail = client.offer_detail(offer_id)
    if not detail:
        log.warning(f"Could not fetch details for {offer_id}")
        return {'status': 'error', 'reason': 'detail_fetch_failed'}
    
    # Small delay between API calls to be respectful
    time.sleep(random.uniform(1.5, 4.0))
    
    # Score the listing
    score_result = score_listing(offer, detail)
    total_score = score_result['total_score']
    log.info(f"  Score: {total_score}/100")

    # ── Tier 1: Below notify threshold → ignore completely ───────────
    if total_score < config.SCORE_NOTIFY_ONLY:
        log.info(f"  Below {config.SCORE_NOTIFY_ONLY}, ignoring")
        return {'status': 'ignored', 'score': total_score}

    # ── Tier 2: Notify-only range (50-64) → email alert, no message ──
    if total_score < config.SCORE_AUTO_SEND:
        log.info(f"  Score {total_score} is in notify-only range ({config.SCORE_NOTIFY_ONLY}-{config.SCORE_AUTO_SEND - 1})")
        log_result(
            offer, detail, score_result,
            "(not sent automatically — review and apply manually if interested)",
            status="notify_only"
        )
        return {'status': 'notify_only', 'score': total_score}

    # ── Tier 3: Auto-send (65+) → generate message + schedule send ───
    log.info(f"  Score {total_score} >= {config.SCORE_AUTO_SEND}, auto-sending")

    # Extract poster name for personalization
    poster_name = None
    for key in ['first_name', 'user_name', 'poster_name', 'contact_name', 'name']:
        val = detail.get(key) or offer.get(key)
        if val and str(val).strip():
            poster_name = str(val).strip()
            break

    # Extract description for message generation
    desc_parts = []
    for key in ['freetext_property_description', 'freetext_wg_description',
                'freetext_district', 'freetext_misc', 'description', 'ad_description']:
        if key in detail and detail[key]:
            desc_parts.append(str(detail[key]))
    description = '\n'.join(desc_parts)

    # Generate personalized message
    log.info(f"  Generating personalized message...")
    message = generate_message(title, description, detail, poster_name)
    log.info(f"  Message generated ({len(message)} chars)")

    # Schedule with random delay
    delay_minutes = random.randint(config.MESSAGE_DELAY_MIN, config.MESSAGE_DELAY_MAX)
    send_at = time.time() + (delay_minutes * 60)

    # Save to pending messages
    pending = load_json(config.PENDING_FILE, default=[])
    pending.append({
        'offer_id': offer_id,
        'title': title,
        'message': message,
        'send_at': send_at,
        'send_at_human': datetime.fromtimestamp(send_at, timezone.utc).isoformat(),
        'created_at': datetime.now(timezone.utc).isoformat(),
        'status': 'pending'
    })
    save_json(config.PENDING_FILE, pending)

    log.info(f"  Message scheduled for delivery in {delay_minutes} minutes")

    # Log for daily email recap
    log_result(
        offer, detail, score_result, message,
        status=f"scheduled (sending in ~{delay_minutes} min)"
    )

    return {'status': 'scheduled', 'score': total_score, 'delay': delay_minutes}


# ─── Send Pending Messages ────────────────────────────────────────────
def process_pending_messages(client: WgGesuchtClient):
    """Check for pending messages that are due and send them."""
    pending = load_json(config.PENDING_FILE, default=[])
    if not pending:
        return
    
    now = time.time()
    updated = False
    
    for item in pending:
        if item['status'] != 'pending':
            continue
        
        if now >= item['send_at']:
            offer_id = item['offer_id']
            message = item['message']
            
            log.info(f"Sending scheduled message for offer {offer_id}...")
            
            # Small random delay before sending
            time.sleep(random.uniform(2.0, 8.0))
            
            result = client.contact_offer(offer_id, message)
            
            if result is not None:
                item['status'] = 'sent'
                item['sent_at'] = datetime.now(timezone.utc).isoformat()
                log.info(f"  Message sent successfully!")
                
                # Log successful send
                log_status(
                    f"Message sent for: {item['title']} (Offer {offer_id})"
                )
            else:
                item['status'] = 'failed'
                item['failed_at'] = datetime.now(timezone.utc).isoformat()
                log.error(f"  Failed to send message for offer {offer_id}")
                
                log_status(
                    f"FAILED to send for: {item['title']} (Offer {offer_id}) — send manually"
                )
            
            updated = True
            
            # Delay between sends
            time.sleep(random.uniform(5.0, 15.0))
    
    if updated:
        save_json(config.PENDING_FILE, pending)
    
    # Clean up old entries (keep last 200)
    if len(pending) > 200:
        pending = [p for p in pending if p['status'] == 'pending'] + \
                  [p for p in pending if p['status'] != 'pending'][-100:]
        save_json(config.PENDING_FILE, pending)


# ─── Main ──────────────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info("WG-Gesucht Bot starting...")
    log.info(f"Time: {datetime.now(timezone.utc).isoformat()}")
    
    # Authenticate
    client = get_client()
    if not client:
        log.error("Could not authenticate. Exiting.")
        return
    
    # Step 1: Send any pending messages that are due
    log.info("Checking for pending messages to send...")
    process_pending_messages(client)
    
    # Step 2: Fetch and process new listings
    new_listings = fetch_new_listings(client)
    
    results = {'scheduled': 0, 'notify_only': 0, 'ignored': 0, 'errors': 0}

    for offer in new_listings:
        try:
            result = process_listing(client, offer)
            status = result.get('status', 'error')
            if status in results:
                results[status] += 1
            else:
                results['errors'] += 1
        except Exception as e:
            log.error(f"Error processing offer: {e}", exc_info=True)
            results['errors'] += 1

        # Delay between processing listings
        time.sleep(random.uniform(2.0, 5.0))

    # Save updated session (tokens may have been refreshed)
    save_json(config.SESSION_FILE, client.export_account())

    # Summary
    log.info(f"Run complete: {results['scheduled']} auto-send, "
             f"{results['notify_only']} notify-only, "
             f"{results['ignored']} ignored, {results['errors']} errors")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
