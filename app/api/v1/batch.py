"""
Batch processing endpoints for offline-first synchronization
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from pymongo.database import Database
from pymongo.errors import BulkWriteError
import logging

from app.database import get_database
from app.api.deps import get_current_active_user
from app.models.user import UserModel
from app.utils.date_utils import get_utc_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/batch", tags=["batch"])


# Batch Request Models
class RoutineCompletionBatch(BaseModel):
    routine_id: str
    completed_steps: List[int]
    skipped_steps: List[int]
    completed_at: datetime
    duration_minutes: int
    mood: Optional[str] = None
    skin_feel: Optional[str] = None


class GoalProgressBatch(BaseModel):
    goal_id: str
    current_value: float
    previous_value: float
    updated_at: datetime
    update_reason: str
    metadata: Optional[Dict[str, Any]] = None


class ReminderActionBatch(BaseModel):
    reminder_id: str
    action: str  # 'completed', 'dismissed', 'snoozed'
    action_at: datetime
    snooze_duration_minutes: Optional[int] = None


class AnalyticsEventBatch(BaseModel):
    event_type: str
    event_name: str
    properties: Dict[str, Any]
    timestamp: datetime
    session_id: Optional[str] = None


class ProductInteractionBatch(BaseModel):
    product_id: str
    interaction_type: str  # 'viewed', 'liked', 'saved', 'purchased'
    timestamp: datetime
    skin_analysis_id: Optional[str] = None
    view_duration_seconds: Optional[int] = None
    product_data: Optional[Dict[str, Any]] = None


class BatchResponse(BaseModel):
    processed: int
    successful: int
    failed: int
    errors: List[Dict[str, Any]] = []
    results: List[Dict[str, Any]] = []


# Batch Endpoints

@router.post("/routine-completions", response_model=BatchResponse)
async def batch_routine_completions(
    completions: List[RoutineCompletionBatch],
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """
    Process multiple routine completions efficiently.
    Handles out-of-order completions and updates streaks.
    """
    logger.info(f"Processing {len(completions)} routine completions for user {current_user.id}")
    
    results = []
    errors = []
    successful = 0
    
    try:
        # Sort completions by timestamp to process in order
        sorted_completions = sorted(completions, key=lambda x: x.completed_at)
        
        for completion in sorted_completions:
            try:
                # Validate completion timestamp isn't in future
                if completion.completed_at > get_utc_now():
                    errors.append({
                        'routine_id': completion.routine_id,
                        'error': 'Completion timestamp cannot be in the future'
                    })
                    continue
                
                # Get the routine
                routine = await db.routines.find_one({
                    '_id': completion.routine_id,
                    'user_id': str(current_user.id)
                })
                
                if not routine:
                    errors.append({
                        'routine_id': completion.routine_id,
                        'error': 'Routine not found'
                    })
                    continue
                
                # Check if this completion already exists (deduplication)
                existing = await db.routine_completions.find_one({
                    'routine_id': completion.routine_id,
                    'user_id': str(current_user.id),
                    'completed_at': {
                        '$gte': completion.completed_at - timedelta(minutes=1),
                        '$lte': completion.completed_at + timedelta(minutes=1)
                    }
                })
                
                if existing:
                    logger.info(f"Skipping duplicate completion for routine {completion.routine_id}")
                    results.append({
                        'routine_id': completion.routine_id,
                        'status': 'skipped',
                        'reason': 'duplicate'
                    })
                    continue
                
                # Create completion record
                completion_doc = {
                    'routine_id': completion.routine_id,
                    'user_id': str(current_user.id),
                    'completed_steps': completion.completed_steps,
                    'skipped_steps': completion.skipped_steps,
                    'completed_at': completion.completed_at,
                    'duration_minutes': completion.duration_minutes,
                    'mood': completion.mood,
                    'skin_feel': completion.skin_feel,
                    'created_at': get_utc_now()
                }
                
                await db.routine_completions.insert_one(completion_doc)
                
                # Update routine stats
                last_completed = routine.get('last_completed')
                completion_count = routine.get('completion_count', 0) + 1
                
                # Calculate streak
                streak = routine.get('completion_streak', 0)
                if last_completed:
                    days_diff = (completion.completed_at - last_completed).days
                    if days_diff <= 1:
                        streak += 1
                    else:
                        streak = 1
                else:
                    streak = 1
                
                # Update routine
                await db.routines.update_one(
                    {'_id': completion.routine_id},
                    {
                        '$set': {
                            'last_completed': completion.completed_at,
                            'completion_count': completion_count,
                            'completion_streak': streak,
                            'updated_at': get_utc_now()
                        }
                    }
                )
                
                # Update goals related to this routine
                await _update_goals_from_routine(
                    completion.routine_id,
                    str(current_user.id),
                    db
                )
                
                results.append({
                    'routine_id': completion.routine_id,
                    'status': 'success',
                    'completion_count': completion_count,
                    'streak': streak
                })
                successful += 1
                
            except Exception as e:
                logger.error(f"Error processing routine completion: {str(e)}")
                errors.append({
                    'routine_id': completion.routine_id,
                    'error': str(e)
                })
    
    except Exception as e:
        logger.error(f"Batch routine completions error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing batch: {str(e)}"
        )
    
    return BatchResponse(
        processed=len(completions),
        successful=successful,
        failed=len(errors),
        errors=errors,
        results=results
    )


@router.post("/goal-progress", response_model=BatchResponse)
async def batch_goal_progress(
    progress_updates: List[GoalProgressBatch],
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """
    Process multiple goal progress updates.
    Handles conflict resolution and milestone tracking.
    """
    logger.info(f"Processing {len(progress_updates)} goal updates for user {current_user.id}")
    
    results = []
    errors = []
    successful = 0
    
    try:
        # Group updates by goal_id to handle multiple updates for same goal
        updates_by_goal = {}
        for update in progress_updates:
            if update.goal_id not in updates_by_goal:
                updates_by_goal[update.goal_id] = []
            updates_by_goal[update.goal_id].append(update)
        
        for goal_id, updates in updates_by_goal.items():
            try:
                # Get the goal
                goal = await db.goals.find_one({
                    '_id': goal_id,
                    'user_id': str(current_user.id)
                })
                
                if not goal:
                    errors.append({
                        'goal_id': goal_id,
                        'error': 'Goal not found'
                    })
                    continue
                
                # Sort updates by timestamp
                sorted_updates = sorted(updates, key=lambda x: x.updated_at)
                
                # Apply updates in order
                final_value = goal.get('current_value', 0)
                for update in sorted_updates:
                    # Conflict resolution: Use highest value (optimistic)
                    if update.current_value > final_value:
                        final_value = update.current_value
                    
                    # Record progress history
                    progress_doc = {
                        'goal_id': goal_id,
                        'user_id': str(current_user.id),
                        'previous_value': update.previous_value,
                        'current_value': update.current_value,
                        'updated_at': update.updated_at,
                        'update_reason': update.update_reason,
                        'metadata': update.metadata,
                        'created_at': get_utc_now()
                    }
                    await db.goal_progress.insert_one(progress_doc)
                
                # Calculate progress percentage
                baseline_value = goal.get('baseline_value', 0)
                target_value = goal.get('target_value', 100)
                
                if target_value != baseline_value:
                    progress_percentage = ((final_value - baseline_value) / 
                                         (target_value - baseline_value)) * 100
                    progress_percentage = max(0, min(100, progress_percentage))
                else:
                    progress_percentage = 100 if final_value >= target_value else 0
                
                # Check milestones
                milestones_achieved = []
                if 'milestones' in goal:
                    for milestone in goal['milestones']:
                        if not milestone.get('is_completed', False):
                            if final_value >= milestone.get('target_value', 0):
                                milestone['is_completed'] = True
                                milestone['completed_at'] = get_utc_now()
                                milestones_achieved.append(milestone['name'])
                
                # Update goal
                update_doc = {
                    'current_value': final_value,
                    'progress_percentage': progress_percentage,
                    'last_updated': get_utc_now(),
                    'updated_at': get_utc_now()
                }
                
                if milestones_achieved:
                    update_doc['milestones'] = goal['milestones']
                
                # Check if goal is completed
                if progress_percentage >= 100 and goal.get('status') == 'active':
                    update_doc['status'] = 'completed'
                    update_doc['completed_at'] = get_utc_now()
                
                await db.goals.update_one(
                    {'_id': goal_id},
                    {'$set': update_doc}
                )
                
                results.append({
                    'goal_id': goal_id,
                    'status': 'success',
                    'final_value': final_value,
                    'progress_percentage': progress_percentage,
                    'milestones_achieved': milestones_achieved
                })
                successful += 1
                
            except Exception as e:
                logger.error(f"Error processing goal progress: {str(e)}")
                errors.append({
                    'goal_id': goal_id,
                    'error': str(e)
                })
    
    except Exception as e:
        logger.error(f"Batch goal progress error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing batch: {str(e)}"
        )
    
    return BatchResponse(
        processed=len(progress_updates),
        successful=successful,
        failed=len(errors),
        errors=errors,
        results=results
    )


@router.post("/analytics", response_model=BatchResponse)
async def batch_analytics(
    events: List[AnalyticsEventBatch],
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """
    Process analytics events in batch.
    Stores events for later analysis and reporting.
    """
    logger.info(f"Processing {len(events)} analytics events for user {current_user.id}")
    
    results = []
    errors = []
    successful = 0
    
    try:
        # Prepare batch insert
        documents = []
        for event in events:
            doc = {
                'user_id': str(current_user.id),
                'event_type': event.event_type,
                'event_name': event.event_name,
                'properties': event.properties,
                'timestamp': event.timestamp,
                'session_id': event.session_id,
                'created_at': get_utc_now()
            }
            documents.append(doc)
        
        # Bulk insert
        if documents:
            result = await db.analytics_events.insert_many(documents)
            successful = len(result.inserted_ids)
            
            # Update user engagement metrics
            await _update_user_engagement(str(current_user.id), events, db)
            
            results.append({
                'status': 'success',
                'events_processed': successful
            })
    
    except BulkWriteError as e:
        logger.error(f"Bulk write error: {str(e)}")
        successful = e.details.get('nInserted', 0)
        errors.append({
            'error': 'Partial write failure',
            'details': str(e)
        })
    except Exception as e:
        logger.error(f"Batch analytics error: {str(e)}")
        errors.append({
            'error': str(e)
        })
    
    return BatchResponse(
        processed=len(events),
        successful=successful,
        failed=len(events) - successful,
        errors=errors,
        results=results
    )


@router.post("/reminders", response_model=BatchResponse)
async def batch_reminder_actions(
    actions: List[ReminderActionBatch],
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """
    Process reminder actions in batch.
    Handles completed, dismissed, and snoozed reminders.
    """
    logger.info(f"Processing {len(actions)} reminder actions for user {current_user.id}")
    
    results = []
    errors = []
    successful = 0
    
    for action in actions:
        try:
            # Get the reminder
            reminder = await db.reminders.find_one({
                '_id': action.reminder_id,
                'user_id': str(current_user.id)
            })
            
            if not reminder:
                errors.append({
                    'reminder_id': action.reminder_id,
                    'error': 'Reminder not found'
                })
                continue
            
            # Process action
            update_doc = {}
            
            if action.action == 'completed':
                update_doc = {
                    'status': 'completed',
                    'completed_at': action.action_at,
                    'updated_at': get_utc_now()
                }
            elif action.action == 'dismissed':
                update_doc = {
                    'status': 'dismissed',
                    'dismissed_at': action.action_at,
                    'updated_at': get_utc_now()
                }
            elif action.action == 'snoozed':
                snooze_until = action.action_at + timedelta(
                    minutes=action.snooze_duration_minutes or 15
                )
                update_doc = {
                    'status': 'snoozed',
                    'snoozed_until': snooze_until,
                    'updated_at': get_utc_now()
                }
            
            # Update reminder
            await db.reminders.update_one(
                {'_id': action.reminder_id},
                {'$set': update_doc}
            )
            
            # Record action history
            history_doc = {
                'reminder_id': action.reminder_id,
                'user_id': str(current_user.id),
                'action': action.action,
                'action_at': action.action_at,
                'created_at': get_utc_now()
            }
            await db.reminder_history.insert_one(history_doc)
            
            results.append({
                'reminder_id': action.reminder_id,
                'status': 'success',
                'action': action.action
            })
            successful += 1
            
        except Exception as e:
            logger.error(f"Error processing reminder action: {str(e)}")
            errors.append({
                'reminder_id': action.reminder_id,
                'error': str(e)
            })
    
    return BatchResponse(
        processed=len(actions),
        successful=successful,
        failed=len(errors),
        errors=errors,
        results=results
    )


@router.post("/product-interactions", response_model=BatchResponse)
async def batch_product_interactions(
    interactions: List[ProductInteractionBatch],
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """
    Process product interactions in batch.
    Updates user preferences and product analytics.
    """
    logger.info(f"Processing {len(interactions)} product interactions for user {current_user.id}")
    
    results = []
    errors = []
    successful = 0
    
    try:
        # Prepare batch insert
        documents = []
        for interaction in interactions:
            doc = {
                'user_id': str(current_user.id),
                'product_id': interaction.product_id,
                'interaction_type': interaction.interaction_type,
                'timestamp': interaction.timestamp,
                'skin_analysis_id': interaction.skin_analysis_id,
                'view_duration_seconds': interaction.view_duration_seconds,
                'product_data': interaction.product_data,
                'created_at': get_utc_now()
            }
            documents.append(doc)
        
        # Bulk insert
        if documents:
            result = await db.product_interactions.insert_many(documents)
            successful = len(result.inserted_ids)
            
            # Update user product preferences
            await _update_user_product_preferences(
                str(current_user.id),
                interactions,
                db
            )
            
            results.append({
                'status': 'success',
                'interactions_processed': successful
            })
    
    except BulkWriteError as e:
        logger.error(f"Bulk write error: {str(e)}")
        successful = e.details.get('nInserted', 0)
        errors.append({
            'error': 'Partial write failure',
            'details': str(e)
        })
    except Exception as e:
        logger.error(f"Batch product interactions error: {str(e)}")
        errors.append({
            'error': str(e)
        })
    
    return BatchResponse(
        processed=len(interactions),
        successful=successful,
        failed=len(interactions) - successful,
        errors=errors,
        results=results
    )


# Helper functions

async def _update_goals_from_routine(
    routine_id: str,
    user_id: str,
    db: Database
):
    """Update goals based on routine completion"""
    try:
        # Find goals related to consistency
        consistency_goals = await db.goals.find({
            'user_id': user_id,
            'metric_type': 'consistency',
            'status': 'active'
        }).to_list(None)
        
        for goal in consistency_goals:
            # Get routine completion count for the period
            start_date = goal.get('start_date', datetime.min)
            completions = await db.routine_completions.count_documents({
                'user_id': user_id,
                'completed_at': {'$gte': start_date}
            })
            
            # Update goal progress
            await db.goals.update_one(
                {'_id': goal['_id']},
                {
                    '$set': {
                        'current_value': completions,
                        'last_updated': get_utc_now()
                    }
                }
            )
    except Exception as e:
        logger.error(f"Error updating goals from routine: {str(e)}")


async def _update_user_engagement(
    user_id: str,
    events: List[AnalyticsEventBatch],
    db: Database
):
    """Update user engagement metrics based on analytics events"""
    try:
        # Count events by type
        event_counts = {}
        for event in events:
            event_type = event.event_type
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        # Update user engagement document
        engagement_doc = {
            'user_id': user_id,
            'date': get_utc_now().date(),
            'event_counts': event_counts,
            'total_events': len(events),
            'updated_at': get_utc_now()
        }
        
        await db.user_engagement.update_one(
            {
                'user_id': user_id,
                'date': engagement_doc['date']
            },
            {
                '$inc': {
                    'total_events': len(events)
                },
                '$set': {
                    'updated_at': get_utc_now()
                }
            },
            upsert=True
        )
    except Exception as e:
        logger.error(f"Error updating user engagement: {str(e)}")


async def _update_user_product_preferences(
    user_id: str,
    interactions: List[ProductInteractionBatch],
    db: Database
):
    """Update user product preferences based on interactions"""
    try:
        # Group interactions by type
        liked_products = []
        saved_products = []
        purchased_products = []
        
        for interaction in interactions:
            if interaction.interaction_type == 'liked':
                liked_products.append(interaction.product_id)
            elif interaction.interaction_type == 'saved':
                saved_products.append(interaction.product_id)
            elif interaction.interaction_type == 'purchased':
                purchased_products.append(interaction.product_id)
        
        # Update user preferences
        update_doc = {}
        if liked_products:
            update_doc['$addToSet'] = {'liked_products': {'$each': liked_products}}
        if saved_products:
            update_doc.setdefault('$addToSet', {})['saved_products'] = {'$each': saved_products}
        if purchased_products:
            update_doc.setdefault('$addToSet', {})['purchased_products'] = {'$each': purchased_products}
        
        if update_doc:
            update_doc['$set'] = {'preferences_updated_at': get_utc_now()}
            
            await db.user_product_preferences.update_one(
                {'user_id': user_id},
                update_doc,
                upsert=True
            )
    except Exception as e:
        logger.error(f"Error updating user product preferences: {str(e)}")