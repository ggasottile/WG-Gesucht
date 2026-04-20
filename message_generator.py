"""
Personalized message generator using OpenAI API.
Generates a unique, friendly message for each listing based on
the listing details and the user's personal info.
"""

import json
import os
import re

import config

# We'll use a simple HTTP call to OpenAI to avoid extra dependencies
import requests


OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

SYSTEM_PROMPT = """You are helping someone write a friendly, personal message to apply for an apartment/room listing on WG-Gesucht.de in Munich, Germany.

RULES:
- Write the message in German (the user has B1 German, so use simple but correct German — not overly formal, not childish)
- If the listing is clearly written in English, write the message in English instead
- Keep it 4-8 sentences, warm and genuine — NOT generic or template-y
- Start with a greeting using the landlord/poster's name if available
- Mention 1-2 specific things from the listing that appeal to you (location, description of the flat, WG vibe, etc.)
- Briefly introduce yourself using the personal info provided
- End by expressing interest in meeting in person / visiting the place
- Do NOT use overly formal language (no "Sehr geehrte Damen und Herren")
- Do NOT include a subject line — just the message body
- Do NOT mention that you're using a bot or automation
- Sound natural and human — like a real person who read the listing and is genuinely interested
"""


def generate_message(listing_title: str, listing_description: str, 
                     listing_details: dict, poster_name: str = None) -> str:
    """
    Generate a personalized message for a listing.
    Falls back to a template if OpenAI is unavailable.
    """
    if OPENAI_API_KEY:
        try:
            return _generate_with_openai(listing_title, listing_description, 
                                         listing_details, poster_name)
        except Exception as e:
            print(f"OpenAI generation failed: {e}")
    
    # Fallback to template
    return _generate_template(poster_name)


def _generate_with_openai(title, description, details, poster_name):
    """Generate message using OpenAI API."""
    
    # Build context about the listing
    listing_context = f"Listing title: {title}\n"
    if poster_name:
        listing_context += f"Posted by: {poster_name}\n"
    
    # Add key details
    for key in ['total_rent', 'rent', 'size', 'room_size', 'district', 
                'address', 'category', 'available_from']:
        if key in details and details[key]:
            listing_context += f"{key}: {details[key]}\n"
    
    if description:
        # Truncate very long descriptions
        desc_truncated = description[:2000] if len(description) > 2000 else description
        listing_context += f"\nListing description:\n{desc_truncated}\n"
    
    user_prompt = f"""Write a message to apply for this listing.

LISTING INFO:
{listing_context}

ABOUT ME (use this to personalize):
{config.PERSONAL_INFO}

Write the message now. Just the message text, nothing else."""

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.85,
            "max_tokens": 500
        },
        timeout=30
    )
    response.raise_for_status()
    result = response.json()
    return result['choices'][0]['message']['content'].strip()


def _generate_template(poster_name=None):
    """Fallback template message if OpenAI is unavailable."""
    greeting = f"Hallo {poster_name}" if poster_name else "Hallo"
    
    return f"""{greeting},

ich habe deine Anzeige auf WG-Gesucht gesehen und sie hat mich sofort angesprochen! Ich bin Gianluigi, 24 Jahre alt und arbeite als Berater hier in München.

Zu mir: Ich bin ein offener und unkomplizierter Typ, der sich leicht mit anderen versteht. Ich habe eine feste Routine, mein Zimmer und die gemeinsamen Räume einmal pro Woche gründlich zu putzen. Ich koche sehr gerne und verbringe gerne Zeit in der Küche — natürlich stimme ich mich gerne ab, falls die Küche geteilt wird.

Mein Deutsch ist auf B1-Niveau und ich nehme aktuell Kurse, um es weiter zu verbessern. Unter der Woche gehe ich meistens zwischen 23 und 0 Uhr ins Bett.

Ich würde mich sehr freuen, die Wohnung persönlich anzuschauen und dich kennenzulernen. Wann passt es dir am besten?

Liebe Grüße
Gianluigi"""
