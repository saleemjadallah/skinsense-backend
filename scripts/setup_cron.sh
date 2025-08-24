#!/bin/bash

# Setup cron job for daily reminder generation
# Run this script on the EC2 server after deployment

echo "Setting up daily reminder generation cron job..."

# Create log directory if it doesn't exist
sudo mkdir -p /var/log/skinsense
sudo chown $USER:$USER /var/log/skinsense

# Add cron job for daily reminder generation at 6 AM
(crontab -l 2>/dev/null; echo "# SkinSense AI Daily Reminder Generation") | crontab -
(crontab -l 2>/dev/null; echo "0 6 * * * cd ~/skinsense-backend && /usr/bin/python3 scripts/generate_daily_reminders.py >> /var/log/skinsense/reminders.log 2>&1") | crontab -

# Also add a test run every hour for initial testing (can be removed later)
(crontab -l 2>/dev/null; echo "# Hourly test run (remove after confirming it works)") | crontab -
(crontab -l 2>/dev/null; echo "0 * * * * cd ~/skinsense-backend && /usr/bin/python3 scripts/generate_daily_reminders.py >> /var/log/skinsense/reminders_hourly.log 2>&1") | crontab -

echo "Cron jobs added successfully!"
echo ""
echo "Current crontab:"
crontab -l
echo ""
echo "Logs will be written to:"
echo "  - Daily (6 AM): /var/log/skinsense/reminders.log"
echo "  - Hourly test: /var/log/skinsense/reminders_hourly.log"
echo ""
echo "To monitor logs in real-time:"
echo "  tail -f /var/log/skinsense/reminders.log"
echo ""
echo "To remove the hourly test cron after confirming it works:"
echo "  crontab -e  # Then delete the hourly line"