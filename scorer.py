"""
Scoring engine for WG-Gesucht listings.
Scores each listing 0-100 based on user preferences.

Point distribution:
  Rent:       /30
  Location:   /25
  Size:       /25
  WG size:    /20
  ─────────────────
  Total:     /100
"""

import config


def score_listing(offer: dict, detail: dict) -> dict:
    """
    Score a listing based on preferences. Returns a dict with:
    - total_score (0-100)
    - breakdown: dict of individual scores with reasons
    """
    breakdown = {}

    # ── 1. Rent Score (0-30 points) ──────────────────────────────────
    rent = _extract_rent(offer, detail)
    if rent is not None:
        if rent <= config.IDEAL_RENT_MAX:
            if rent >= config.IDEAL_RENT_MIN:
                rent_score = 30  # Sweet spot
            else:
                rent_score = 25  # Very cheap, might be too good to be true
        elif rent <= int(config.MAX_RENT):
            # Linear decrease from 30 to 10 as rent goes from ideal max to budget max
            ratio = (rent - config.IDEAL_RENT_MAX) / (int(config.MAX_RENT) - config.IDEAL_RENT_MAX + 1)
            rent_score = int(30 - 20 * ratio)
        else:
            rent_score = 0  # Over budget
        breakdown['rent'] = {'score': rent_score, 'max': 30, 'value': f'€{rent}'}
    else:
        rent_score = 15  # Unknown rent, neutral
        breakdown['rent'] = {'score': rent_score, 'max': 30, 'value': 'unknown'}

    # ── 2. Location Score (0-25 points) ──────────────────────────────
    district = _extract_district(offer, detail)
    if district:
        district_lower = district.lower()
        if any(pref in district_lower for pref in config.PREFERRED_DISTRICTS):
            loc_score = 25
        else:
            loc_score = 10  # Munich but not preferred district
        breakdown['location'] = {'score': loc_score, 'max': 25, 'value': district}
    else:
        loc_score = 12
        breakdown['location'] = {'score': loc_score, 'max': 25, 'value': 'unknown'}

    # ── 3. Size Score (0-25 points) ──────────────────────────────────
    size = _extract_size(offer, detail)
    if size is not None:
        if size >= 15:
            size_score = 25  # 15m² or above = max
        elif size >= 12:
            size_score = 15  # Tight but livable
        elif size >= 10:
            size_score = 8   # Very small
        else:
            size_score = 3   # Tiny
        breakdown['size'] = {'score': size_score, 'max': 25, 'value': f'{size}m²'}
    else:
        size_score = 12
        breakdown['size'] = {'score': size_score, 'max': 25, 'value': 'unknown'}

    # ── 4. WG Composition Score (0-20 points) ────────────────────────
    # flatshare_inhabitants_total = total WG size INCLUDING the new person
    # So 2 = 2er WG (you + 1 flatmate), 3 = 3er WG, etc.
    category = _extract_category(offer)
    if category == 0:  # WG room
        wg_total = _extract_flatmate_count(offer, detail)
        if wg_total is not None:
            if wg_total <= 2:
                wg_score = 15  # 2er WG (you + 1)
            elif wg_total == 3:
                wg_score = 10  # 3er WG
            else:
                wg_score = 0   # 4+ people — no points
            breakdown['wg_size'] = {'score': wg_score, 'max': 20, 'value': f'{wg_total}er WG'}
        else:
            wg_score = 8
            breakdown['wg_size'] = {'score': wg_score, 'max': 20, 'value': 'unknown'}
    else:
        # Own apartment — max score
        wg_score = 20
        breakdown['wg_size'] = {'score': wg_score, 'max': 20, 'value': 'own apartment'}

    total = rent_score + loc_score + size_score + wg_score

    return {
        'total_score': min(total, 100),
        'breakdown': breakdown
    }


def _extract_rent(offer, detail):
    """Extract total rent from offer/detail."""
    for obj in [detail, offer]:
        if not obj:
            continue
        for key in ['total_costs', 'rent_costs', 'total_rent', 'rent']:
            if key in obj:
                try:
                    val = obj[key]
                    if isinstance(val, dict):
                        for subkey in ['total', 'rent', 'amount']:
                            if subkey in val:
                                return float(val[subkey])
                    return float(val)
                except (ValueError, TypeError):
                    continue
    return None


def _extract_district(offer, detail):
    """Extract district/neighborhood."""
    for obj in [detail, offer]:
        if not obj:
            continue
        for key in ['district_custom', 'district', 'quarter', 'city_quarter']:
            if key in obj and obj[key]:
                return str(obj[key])
    return None


def _extract_size(offer, detail):
    """Extract room/apartment size in m²."""
    for obj in [detail, offer]:
        if not obj:
            continue
        for key in ['property_size', 'size', 'room_size', 'total_size']:
            if key in obj:
                try:
                    return float(obj[key])
                except (ValueError, TypeError):
                    continue
    return None


def _extract_category(offer):
    """Extract listing category (0=WG, 1=1-Zimmer, 2=Wohnung, 3=Haus)."""
    if offer and 'category' in offer:
        try:
            return int(offer['category'])
        except (ValueError, TypeError):
            pass
    return None


def _extract_flatmate_count(offer, detail):
    """Extract total WG size (including the new person)."""
    for obj in [offer, detail]:
        if not obj:
            continue
        for key in ['flatshare_inhabitants_total', 'flatmate_count', 'roommate_count']:
            if key in obj:
                try:
                    return int(obj[key])
                except (ValueError, TypeError):
                    continue
    return None


def format_score_summary(score_result: dict) -> str:
    """Format a human-readable score summary."""
    lines = [f"*Total Score: {score_result['total_score']}/100*"]
    for name, info in score_result['breakdown'].items():
        lines.append(f"  {name}: {info['score']}/{info['max']} ({info['value']})")
    return '\n'.join(lines)
