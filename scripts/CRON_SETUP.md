# Daily Reminder Generation Setup

## Automatic Daily Generation

### 1. Quick Setup (Recommended)
SSH into your EC2 server and run:
```bash
cd ~/skinsense-backend
chmod +x scripts/setup_cron.sh
./scripts/setup_cron.sh
```

This will automatically set up:
- Daily generation at 6 AM
- Hourly test runs (can be removed after testing)
- Log files in `/var/log/skinsense/`

### 2. Manual Cron Setup
If you prefer to set it up manually:

```bash
# Open crontab editor
crontab -e

# Add this line for daily generation at 6 AM
0 6 * * * cd ~/skinsense-backend && /usr/bin/python3 scripts/generate_daily_reminders.py >> /var/log/skinsense/reminders.log 2>&1
```

### 3. Different Time Zones
Adjust the hour (6) based on your server's timezone:
- Check timezone: `timedatectl`
- Change timezone: `sudo timedatectl set-timezone America/Los_Angeles`

Common timezones:
- LA (PST/PDT): 6 AM = `0 6 * * *`
- NYC (EST/EDT): 6 AM = `0 6 * * *`
- London (GMT/BST): 6 AM = `0 6 * * *`
- Dubai (GST): 6 AM = `0 6 * * *`

## Manual Generation

### Generate for specific user:
```bash
cd ~/skinsense-backend
python3 scripts/generate_reminders_now.py --email support@skinsense.app
```

### Force regeneration (delete existing):
```bash
python3 scripts/generate_reminders_now.py --email support@skinsense.app --force
```

### Generate for all active users:
```bash
python3 scripts/generate_daily_reminders.py
```

## Monitoring

### Check if cron is running:
```bash
# View current crontab
crontab -l

# Check cron service status
systemctl status cron
```

### View logs:
```bash
# Today's reminders
tail -f /var/log/skinsense/reminders.log

# Last 100 lines
tail -100 /var/log/skinsense/reminders.log

# Search for errors
grep ERROR /var/log/skinsense/reminders.log
```

### Check generated reminders in MongoDB:
```bash
# Connect to MongoDB (requires mongosh)
mongosh "mongodb+srv://your-connection-string"

# In MongoDB shell:
use skinpal
db.smart_reminders.find({
  user_id: "6898bdc1d9a3847d8ed38ee9",
  created_at: { $gte: new Date(new Date().setHours(0,0,0,0)) }
}).pretty()
```

## Troubleshooting

### Cron not running?
1. Check cron service: `sudo systemctl restart cron`
2. Check permissions: `ls -la scripts/generate_daily_reminders.py`
3. Make executable: `chmod +x scripts/generate_daily_reminders.py`

### Script errors?
1. Test manually first: `python3 scripts/generate_daily_reminders.py`
2. Check Python path: `which python3`
3. Check environment variables are loaded

### No reminders generated?
1. Check MongoDB connection in logs
2. Verify OpenAI API key is set in `.env`
3. Check if users have logged in recently (30 days)
4. Verify users don't already have reminders for today

## Best Practices

1. **Run at low-traffic times**: 6 AM is usually good
2. **Monitor logs regularly**: Check for errors weekly
3. **Rotate logs**: Set up logrotate for `/var/log/skinsense/`
4. **Test after deployment**: Always run manual test after deploying
5. **Backup before changes**: Keep copy of working crontab

## Log Rotation Setup

Create `/etc/logrotate.d/skinsense`:
```
/var/log/skinsense/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 ubuntu ubuntu
}
```

This keeps 30 days of logs and compresses old ones.