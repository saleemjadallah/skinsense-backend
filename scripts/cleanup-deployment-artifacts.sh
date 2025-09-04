#!/bin/bash

# SkinSense EC2 Deployment Artifacts Cleanup Script
# This script safely removes old deployment artifacts to free up disk space

echo "🧹 Starting deployment artifacts cleanup..."

# Function to print disk usage
print_disk_usage() {
    echo "📊 Current disk usage:"
    df -h /
}

# Show initial disk usage
print_disk_usage
INITIAL_USAGE=$(df / | tail -1 | awk '{print $3}')

# 1. Remove old deployment backups (keep only the 5 most recent)
echo ""
echo "📦 Cleaning old deployment backups..."
cd /home/ubuntu

# Count backup directories
BACKUP_COUNT=$(ls -d skinsense-backend.backup.* 2>/dev/null | wc -l)
OLD_BACKUP_COUNT=$(ls -d skinsense-backend.old.* 2>/dev/null | wc -l)

if [ "$BACKUP_COUNT" -gt 5 ]; then
    echo "Found $BACKUP_COUNT backup directories, keeping the 5 most recent..."
    ls -t skinsense-backend.backup.* | tail -n +6 | while read dir; do
        echo "  Removing: $dir ($(du -sh "$dir" 2>/dev/null | cut -f1))"
        rm -rf "$dir"
    done
else
    echo "✓ Only $BACKUP_COUNT backup directories found (threshold: 5)"
fi

if [ "$OLD_BACKUP_COUNT" -gt 0 ]; then
    echo "Removing $OLD_BACKUP_COUNT old deployment directories..."
    ls skinsense-backend.old.* 2>/dev/null | while read dir; do
        echo "  Removing: $dir ($(du -sh "$dir" 2>/dev/null | cut -f1))"
        rm -rf "$dir"
    done
else
    echo "✓ No old deployment directories found"
fi

# 2. Clean Docker unused images and build cache
echo ""
echo "🐳 Cleaning Docker artifacts..."

# Show Docker disk usage before cleanup
echo "Docker disk usage before cleanup:"
docker system df

# Remove dangling images
echo "Removing dangling images..."
docker image prune -f

# Clean build cache
echo "Cleaning build cache..."
docker builder prune -f

# Remove stopped containers older than 24 hours
echo "Removing old stopped containers..."
docker container prune -f --filter "until=24h"

# Clean unused volumes (careful - only truly unused ones)
echo "Cleaning unused volumes..."
docker volume prune -f

# Show Docker disk usage after cleanup
echo ""
echo "Docker disk usage after cleanup:"
docker system df

# 3. Clean APT package cache
echo ""
echo "📦 Cleaning APT cache..."
sudo apt-get clean
sudo apt-get autoclean -y

# 4. Clean old journal logs (keep last 7 days)
echo ""
echo "📝 Rotating system logs..."
JOURNAL_SIZE_BEFORE=$(sudo journalctl --disk-usage | grep -oP '\d+\.?\d*[MG]')
sudo journalctl --vacuum-time=7d
sudo journalctl --vacuum-size=100M
JOURNAL_SIZE_AFTER=$(sudo journalctl --disk-usage | grep -oP '\d+\.?\d*[MG]')
echo "Journal logs: $JOURNAL_SIZE_BEFORE → $JOURNAL_SIZE_AFTER"

# 5. Remove old kernel packages
echo ""
echo "🔧 Cleaning old kernels..."
CURRENT_KERNEL=$(uname -r)
echo "Current kernel: $CURRENT_KERNEL"
echo "Removing old kernel packages..."
sudo apt-get autoremove -y --purge

# Calculate space recovered
echo ""
echo "✨ Cleanup complete!"
echo ""
print_disk_usage

FINAL_USAGE=$(df / | tail -1 | awk '{print $3}')
RECOVERED=$((INITIAL_USAGE - FINAL_USAGE))

# Convert to MB/GB for display
if [ "$RECOVERED" -gt 1048576 ]; then
    RECOVERED_DISPLAY=$(echo "scale=2; $RECOVERED / 1048576" | bc)
    echo "🎉 Total space recovered: ${RECOVERED_DISPLAY}GB"
elif [ "$RECOVERED" -gt 1024 ]; then
    RECOVERED_DISPLAY=$(echo "scale=2; $RECOVERED / 1024" | bc)
    echo "🎉 Total space recovered: ${RECOVERED_DISPLAY}MB"
else
    echo "🎉 Total space recovered: ${RECOVERED}KB"
fi

# List remaining backups for confirmation
echo ""
echo "📋 Remaining deployment backups:"
ls -lah /home/ubuntu/skinsense-backend.backup.* 2>/dev/null | head -5 || echo "  No backup directories found"

echo ""
echo "✅ Cleanup completed successfully!"