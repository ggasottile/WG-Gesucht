#!/bin/bash
# WG-Gesucht Bot Runner
# This is the entry point for the cron job.

cd "$(dirname "$0")"
python3 bot.py 2>&1
