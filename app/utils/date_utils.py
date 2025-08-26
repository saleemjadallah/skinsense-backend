"""
Universal Date/Time Utilities for SkinSense Backend
Prevents date issues across all AI-generated content and services
Handles MongoDB's requirement for timezone-naive datetimes
"""

from datetime import datetime, timedelta, date, timezone
from typing import Optional, Union
import re
import logging

logger = logging.getLogger(__name__)

def get_utc_now() -> datetime:
    """
    Get current UTC time as timezone-NAIVE datetime for MongoDB compatibility.
    MongoDB stores all datetimes as UTC internally but expects naive datetimes.
    
    Returns:
        datetime: Current UTC time without timezone info (naive)
    """
    # Get current time in UTC then remove timezone info
    # This ensures we have accurate UTC time that works with MongoDB
    return datetime.now(timezone.utc).replace(tzinfo=None)

def get_utc_now_aware() -> datetime:
    """
    Get current UTC time WITH timezone awareness for Python operations.
    Use this for datetime comparisons and calculations in Python code.
    
    Returns:
        datetime: Current UTC time with timezone info (aware)
    """
    return datetime.now(timezone.utc)

def ensure_mongodb_compatible(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure a datetime is compatible with MongoDB (timezone-naive).
    
    Args:
        dt: Datetime object (can be naive or aware)
    
    Returns:
        datetime: Timezone-naive datetime or None
    """
    if dt is None:
        return None
    
    if dt.tzinfo is not None:
        # If timezone-aware, convert to UTC and remove tzinfo
        utc_dt = dt.astimezone(timezone.utc)
        return utc_dt.replace(tzinfo=None)
    
    # Already naive, return as-is
    return dt

def ensure_future_datetime(
    dt_input: Union[str, datetime, date, None],
    default_hours_ahead: int = 2,
    category: Optional[str] = None
) -> datetime:
    """
    Ensure a datetime is in the future, fixing any past dates.
    
    Args:
        dt_input: Input datetime (can be string, datetime, date, or None)
        default_hours_ahead: Hours to add from now if no valid time provided
        category: Optional category for smart scheduling (e.g., 'routine', 'insight')
    
    Returns:
        A datetime guaranteed to be in the future (MongoDB-compatible, timezone-naive)
    """
    now = get_utc_now()  # Already returns naive UTC datetime
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Handle None or empty input
    if not dt_input:
        return now + timedelta(hours=default_hours_ahead)
    
    # Convert input to datetime
    target_dt = None
    
    if isinstance(dt_input, datetime):
        target_dt = dt_input
    elif isinstance(dt_input, date):
        # Convert date to datetime at midnight (keep naive for MongoDB)
        target_dt = datetime.combine(dt_input, datetime.min.time())
    elif isinstance(dt_input, str):
        try:
            # Try various formats
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ]:
                try:
                    target_dt = datetime.strptime(dt_input, fmt)
                    # Keep naive for MongoDB
                    break
                except ValueError:
                    continue
            
            # Try ISO format with timezone
            if not target_dt:
                target_dt = datetime.fromisoformat(dt_input.replace('Z', '+00:00'))
                # Convert to naive UTC if it has timezone
                if target_dt.tzinfo is not None:
                    target_dt = target_dt.astimezone(timezone.utc).replace(tzinfo=None)
            
        except (ValueError, AttributeError) as e:
            logger.warning(f"Could not parse datetime string: {dt_input}")
            # Try to extract time only
            time_match = re.search(r'(\d{1,2}):(\d{2})', str(dt_input))
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                if 0 <= hour < 24 and 0 <= minute < 60:
                    target_dt = today.replace(hour=hour, minute=minute)
    
    # If we couldn't parse, use default
    if not target_dt:
        return now + timedelta(hours=default_hours_ahead)
    
    # Convert to naive UTC if it has timezone info (for MongoDB)
    if target_dt.tzinfo is not None:
        target_dt = target_dt.astimezone(timezone.utc).replace(tzinfo=None)
    
    # Check if date is suspicious (past year or in the past)
    if target_dt.year < now.year or target_dt < now:
        # For past dates, preserve the time but move to today/tomorrow
        hour = target_dt.hour
        minute = target_dt.minute
        
        # Apply time to today
        fixed_dt = today.replace(hour=hour, minute=minute)
        
        # If time has passed today, schedule for tomorrow
        if fixed_dt <= now:
            fixed_dt = fixed_dt + timedelta(days=1)
        
        logger.info(f"Fixed past date: {dt_input} -> {fixed_dt.isoformat()}")
        return fixed_dt
    
    # Date is valid and in the future
    return target_dt

def get_smart_schedule_time(
    category: str,
    priority: Optional[int] = None,
    user_preferences: Optional[dict] = None
) -> datetime:
    """
    Get smart scheduling time based on category and user preferences.
    
    Args:
        category: Type of content ('routine', 'insight', 'reminder', 'goal')
        priority: Priority level (1-10)
        user_preferences: User's scheduling preferences
    
    Returns:
        Smart scheduled datetime
    """
    now = get_utc_now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Default times for different categories
    schedule_map = {
        'routine_morning': 8,
        'routine_evening': 20,
        'insight': 9,  # Morning insights
        'goal': 11,  # Mid-morning for goals
        'photo': 14,  # Afternoon for photos
        'hydration': 12,  # Noon for hydration
        'education': 16,  # Late afternoon for learning
        'achievement': 10,  # Morning celebration
    }
    
    # Get user's preferred times if available
    if user_preferences:
        if 'morning_routine_time' in user_preferences:
            try:
                hour = int(user_preferences['morning_routine_time'].split(':')[0])
                schedule_map['routine_morning'] = hour
            except:
                pass
        
        if 'evening_routine_time' in user_preferences:
            try:
                hour = int(user_preferences['evening_routine_time'].split(':')[0])
                schedule_map['routine_evening'] = hour
            except:
                pass
    
    # Determine scheduled hour based on category
    if category == 'routine':
        # Check if it's morning or evening based on current time
        if now.hour < 12:
            scheduled_hour = schedule_map['routine_morning']
        else:
            scheduled_hour = schedule_map['routine_evening']
    else:
        # Use category-specific time or default
        scheduled_hour = schedule_map.get(category, 14)  # Default to 2 PM
    
    # Adjust based on priority if provided
    if priority:
        if priority >= 8:  # High priority - soon
            return now + timedelta(hours=1)
        elif priority >= 5:  # Medium priority
            return now + timedelta(hours=3)
    
    # Create scheduled time
    scheduled_dt = today.replace(hour=scheduled_hour, minute=0)
    
    # Ensure it's in the future
    if scheduled_dt <= now:
        scheduled_dt = scheduled_dt + timedelta(days=1)
    
    return scheduled_dt

def calculate_expiry_time(
    content_type: str,
    base_time: Optional[datetime] = None
) -> datetime:
    """
    Calculate appropriate expiry time for different content types.
    
    Args:
        content_type: Type of content ('insight', 'reminder', 'recommendation')
        base_time: Base time to calculate from (defaults to now)
    
    Returns:
        Expiry datetime
    """
    if not base_time:
        base_time = get_utc_now()
    
    expiry_map = {
        'insight': timedelta(hours=24),  # Daily insights expire after 24 hours
        'reminder': timedelta(hours=48),  # Reminders valid for 2 days
        'recommendation': timedelta(days=7),  # Product recommendations valid for a week
        'goal': timedelta(days=30),  # Goals valid for a month
        'analysis': timedelta(days=90),  # Analysis results valid for 3 months
    }
    
    expiry_duration = expiry_map.get(content_type, timedelta(hours=24))
    return base_time + expiry_duration

def is_content_expired(
    created_at: datetime,
    content_type: str,
    custom_expiry: Optional[datetime] = None
) -> bool:
    """
    Check if content has expired based on type and creation time.
    
    Args:
        created_at: When the content was created
        content_type: Type of content
        custom_expiry: Optional custom expiry time
    
    Returns:
        True if content has expired
    """
    now = get_utc_now()
    
    if custom_expiry:
        return now > custom_expiry
    
    expiry_time = calculate_expiry_time(content_type, created_at)
    return now > expiry_time

def should_regenerate_content(
    last_generated: Optional[datetime],
    content_type: str,
    force_if_stale_hours: Optional[int] = None
) -> bool:
    """
    Determine if content should be regenerated based on staleness.
    
    Args:
        last_generated: When content was last generated
        content_type: Type of content
        force_if_stale_hours: Force regeneration after this many hours
    
    Returns:
        True if content should be regenerated
    """
    if not last_generated:
        return True
    
    now = get_utc_now()
    
    # Default staleness periods
    stale_map = {
        'insight': 24,  # Regenerate daily insights after 24 hours
        'reminder': 12,  # Regenerate reminders twice daily
        'recommendation': 168,  # Weekly for recommendations
        'goal': 720,  # Monthly for goals
    }
    
    stale_hours = force_if_stale_hours or stale_map.get(content_type, 24)
    time_since = now - last_generated
    
    return time_since.total_seconds() > (stale_hours * 3600)

def get_date_range_for_today() -> tuple[datetime, datetime]:
    """
    Get start and end datetime for today in UTC.
    
    Returns:
        Tuple of (start_of_day, end_of_day) in UTC
    """
    now = get_utc_now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1) - timedelta(microseconds=1)
    return start, end

def format_relative_time(dt: datetime) -> str:
    """
    Format datetime as relative time string (e.g., "in 2 hours", "tomorrow at 9 AM").
    
    Args:
        dt: Datetime to format
    
    Returns:
        Human-readable relative time string
    """
    now = get_utc_now()
    
    # Ensure timezone awareness
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    diff = dt - now
    
    if diff.total_seconds() < 0:
        return "now"
    
    hours = diff.total_seconds() / 3600
    days = diff.days
    
    if hours < 1:
        minutes = int(diff.total_seconds() / 60)
        return f"in {minutes} minutes" if minutes > 1 else "in 1 minute"
    elif hours < 24:
        return f"in {int(hours)} hours" if hours > 1 else "in 1 hour"
    elif days == 1:
        return f"tomorrow at {dt.strftime('%-I:%M %p')}"
    elif days < 7:
        return f"{dt.strftime('%A')} at {dt.strftime('%-I:%M %p')}"
    else:
        return dt.strftime('%B %d at %-I:%M %p')

# Backwards compatibility aliases
utcnow = get_utc_now  # Alias for easy migration from datetime.utcnow()