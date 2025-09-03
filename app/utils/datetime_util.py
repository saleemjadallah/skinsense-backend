"""
DateTime utility class to eliminate redundant datetime calculations
"""
from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class DateTimeUtil:
    """Centralized datetime operations utility"""
    
    @staticmethod
    def now() -> datetime:
        """
        Get current UTC datetime (timezone-aware).
        Replaces deprecated datetime.utcnow()
        """
        return datetime.now(timezone.utc)
    
    @staticmethod
    def today_start() -> datetime:
        """
        Get start of today (00:00:00) in UTC.
        Commonly used for daily aggregations.
        """
        now = DateTimeUtil.now()
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    @staticmethod
    def today_end() -> datetime:
        """
        Get end of today (23:59:59.999999) in UTC.
        """
        now = DateTimeUtil.now()
        return now.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    @staticmethod
    def current_week_range() -> Tuple[datetime, datetime]:
        """
        Get current week's start and end dates (Monday to Sunday).
        Returns tuple of (week_start, week_end).
        """
        today = DateTimeUtil.today_start()
        # Get Monday (0 = Monday, 6 = Sunday)
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
        return week_start, week_end
    
    @staticmethod
    def week_range_for_date(date: datetime) -> Tuple[datetime, datetime]:
        """
        Get week range for a specific date.
        """
        # Ensure we're working with start of day
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = date_start - timedelta(days=date_start.weekday())
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
        return week_start, week_end
    
    @staticmethod
    def days_until(future_date: datetime) -> int:
        """
        Calculate days until a future date from now.
        """
        now = DateTimeUtil.now()
        delta = future_date - now
        return max(0, delta.days)
    
    @staticmethod
    def days_since(past_date: datetime) -> int:
        """
        Calculate days since a past date until now.
        """
        now = DateTimeUtil.now()
        delta = now - past_date
        return max(0, delta.days)
    
    @staticmethod
    def is_same_day(date1: datetime, date2: datetime) -> bool:
        """
        Check if two datetimes are on the same day (ignoring time).
        """
        return date1.date() == date2.date()
    
    @staticmethod
    def is_today(date: datetime) -> bool:
        """
        Check if a datetime is today.
        """
        today = DateTimeUtil.today_start()
        return DateTimeUtil.is_same_day(date, today)
    
    @staticmethod
    def add_weeks(date: datetime, weeks: int) -> datetime:
        """
        Add weeks to a date.
        """
        return date + timedelta(weeks=weeks)
    
    @staticmethod
    def format_iso(date: Optional[datetime]) -> Optional[str]:
        """
        Format datetime to ISO string, handling None values.
        """
        if date is None:
            return None
        # Ensure timezone awareness
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return date.isoformat()
    
    @staticmethod
    def parse_iso(date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse ISO string to datetime, handling None values.
        """
        if not date_str:
            return None
        try:
            # Parse and ensure timezone awareness
            dt = datetime.fromisoformat(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse date string '{date_str}': {e}")
            return None