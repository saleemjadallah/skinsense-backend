"""
Pal AI Chat API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.models.user import UserModel
from app.api.v1.auth import get_current_user
from app.services.pal_service import pal_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pal", tags=["Pal AI Assistant"])

# Request/Response Models
class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="User's message to Pal")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")

class ChatResponse(BaseModel):
    response: str = Field(..., description="Pal's response")
    session_id: str = Field(..., description="Session ID for this conversation")
    timestamp: str = Field(..., description="Response timestamp")
    emotion: str = Field(..., description="Detected emotion for animation")
    suggestions: List[str] = Field(..., description="Follow-up question suggestions")

class ConversationStarter(BaseModel):
    text: str = Field(..., description="Suggested question or topic")
    icon: str = Field(..., description="Emoji icon for the suggestion")

@router.post("/chat", response_model=ChatResponse)
async def chat_with_pal(
    message: ChatMessage,
    current_user: UserModel = Depends(get_current_user)
) -> ChatResponse:
    """
    Send a message to Pal and get a response
    
    Pal can help with:
    - Skincare education and ingredient information
    - Product guidance and routine building
    - Lifestyle and wellness tips
    - Beauty techniques and application tips
    
    Pal cannot provide medical advice or diagnose skin conditions.
    """
    try:
        logger.info(f"User {current_user.id} sending message to Pal")
        
        # Process message with Pal (synchronous call)
        result = pal_service.chat_with_pal(
            user_id=str(current_user.id),
            message=message.message,
            session_id=message.session_id
        )
        
        return ChatResponse(**result)
        
    except Exception as e:
        logger.error(f"Error in Pal chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Pal is taking a quick break. Please try again!"
        )

@router.get("/history")
async def get_chat_history(
    session_id: Optional[str] = None,
    limit: int = 50,
    current_user: UserModel = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get chat history for the current user
    
    Args:
        session_id: Optional specific session ID
        limit: Maximum number of messages to return (default 50)
    """
    try:
        if session_id:
            # Get specific session history (synchronous call)
            history = pal_service._get_session_history(session_id)
            
            # Verify user owns this session
            if history and str(history[0].get("user_id")) != str(current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this session"
                )
        else:
            # Get all user's recent chats (synchronous)
            history = list(pal_service.chat_collection.find(
                {"user_id": current_user.id}
            ).sort("timestamp", -1).limit(limit))
        
        # Format history for response
        formatted_history = []
        for chat in history:
            formatted_history.append({
                "user_message": chat.get("user_message"),
                "pal_response": chat.get("pal_response"),
                "timestamp": chat.get("timestamp").isoformat() if chat.get("timestamp") else None,
                "session_id": chat.get("session_id")
            })
        
        return {
            "history": formatted_history,
            "total_messages": len(formatted_history)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve chat history"
        )

@router.delete("/history")
async def clear_chat_history(
    session_id: Optional[str] = None,
    current_user: UserModel = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Clear chat history for the current user
    
    Args:
        session_id: Optional specific session to clear (if not provided, clears all)
    """
    try:
        success = pal_service.clear_chat_history(
            user_id=str(current_user.id),
            session_id=session_id
        )
        
        if success:
            return {
                "message": "Chat history cleared successfully",
                "cleared": "session" if session_id else "all"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not clear chat history"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not clear chat history"
        )

@router.get("/suggestions", response_model=List[ConversationStarter])
async def get_conversation_starters(
    current_user: UserModel = Depends(get_current_user)
) -> List[ConversationStarter]:
    """
    Get personalized conversation starters based on user's profile and recent activity
    """
    try:
        starters = pal_service.get_conversation_starters(
            user_id=str(current_user.id)
        )
        
        return [ConversationStarter(**starter) for starter in starters]
        
    except Exception as e:
        logger.error(f"Error getting conversation starters: {e}")
        # Return default starters on error
        return [
            ConversationStarter(text="How can I improve my skin?", icon="💧"),
            ConversationStarter(text="What's a good routine for me?", icon="📋"),
            ConversationStarter(text="Tell me about ingredients", icon="🧪"),
            ConversationStarter(text="How do I use this product?", icon="✨")
        ]

@router.post("/feedback")
async def submit_chat_feedback(
    session_id: str,
    message_index: int,
    helpful: bool,
    current_user: UserModel = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Submit feedback on whether Pal's response was helpful
    
    Args:
        session_id: The chat session ID
        message_index: Index of the message in the session
        helpful: Whether the response was helpful
    """
    try:
        # Update the specific chat message with feedback (synchronous)
        result = pal_service.chat_collection.update_one(
            {
                "session_id": session_id,
                "user_id": current_user.id
            },
            {
                "$set": {
                    "helpful": helpful,
                    "feedback_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            return {"message": "Thank you for your feedback!"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat message not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not submit feedback"
        )

@router.get("/stats")
async def get_pal_stats(
    current_user: UserModel = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get user's Pal interaction statistics
    """
    try:
        # Get total message count (synchronous)
        total_messages = pal_service.chat_collection.count_documents(
            {"user_id": current_user.id}
        )
        
        # Get session count
        total_sessions = pal_service.session_collection.count_documents(
            {"user_id": current_user.id}
        )
        
        # Get helpful feedback stats
        helpful_count = pal_service.chat_collection.count_documents(
            {"user_id": current_user.id, "helpful": True}
        )
        
        not_helpful_count = pal_service.chat_collection.count_documents(
            {"user_id": current_user.id, "helpful": False}
        )
        
        # Get most recent session
        recent_session = pal_service.session_collection.find_one(
            {"user_id": current_user.id},
            sort=[("last_activity", -1)]
        )
        
        return {
            "total_messages": total_messages,
            "total_sessions": total_sessions,
            "helpful_responses": helpful_count,
            "not_helpful_responses": not_helpful_count,
            "satisfaction_rate": (helpful_count / (helpful_count + not_helpful_count) * 100) if (helpful_count + not_helpful_count) > 0 else 0,
            "last_chat": recent_session.get("last_activity").isoformat() if recent_session and recent_session.get("last_activity") else None
        }
        
    except Exception as e:
        logger.error(f"Error getting Pal stats: {e}")
        return {
            "total_messages": 0,
            "total_sessions": 0,
            "helpful_responses": 0,
            "not_helpful_responses": 0,
            "satisfaction_rate": 0,
            "last_chat": None
        }