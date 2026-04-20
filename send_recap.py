#!/usr/bin/env python3
"""
Send the daily email recap.
Run this once a day via a separate GitHub Actions job.
"""

import sys
import os

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BOT_DIR)

from notifier import send_daily_recap

send_daily_recap()
