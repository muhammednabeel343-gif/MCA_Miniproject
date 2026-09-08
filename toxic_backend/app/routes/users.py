from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, ChatMessage, GameRoomPlayer, GameSession
from app.services.auth import require_active_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
def get_user_profile(current_user: User = Depends(require_active_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "account_status": current_user.account_status,
        "warning_count": current_user.warning_count,
        "created_at": current_user.created_at
    }


@router.get("/me/stats")
def get_user_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user)
):
    # Total messages
    total_messages = db.query(ChatMessage).filter(ChatMessage.user_id == current_user.id).count()

    # Toxic messages
    toxic_messages = db.query(ChatMessage).filter(
        ChatMessage.user_id == current_user.id,
        ChatMessage.status == "Toxic"
    ).count()

    # Safe messages
    safe_messages = total_messages - toxic_messages

    # Toxicity percentage
    toxicity_percentage = round((toxic_messages / total_messages * 100), 2) if total_messages > 0 else 0.0

    # Total games joined (unique room_ids joined)
    total_games_played = db.query(GameRoomPlayer.room_id).filter(
        GameRoomPlayer.user_id == current_user.id
    ).distinct().count()

    # Let's fetch recent activity: last 5 messages
    recent_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(5)
        .all()
    )

    recent_list = []
    for m in recent_messages:
        recent_list.append({
            "message": m.message,
            "status": m.status,
            "prediction": m.prediction,
            "confidence": m.confidence,
            "game_name": m.game.name if m.game else None,
            "created_at": m.created_at
        })

    # User moderation details
    active_restriction = False
    if current_user.account_status == "RESTRICTED":
        active_restriction = True

    return {
        "total_messages": total_messages,
        "toxic_messages": toxic_messages,
        "safe_messages": safe_messages,
        "toxicity_percentage": toxicity_percentage,
        "total_games_played": total_games_played,
        "warning_count": current_user.warning_count,
        "status": current_user.account_status,
        "recent_messages": recent_list,
        "restricted": active_restriction
    }
