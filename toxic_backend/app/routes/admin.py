from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from backend.app.database import get_db
from backend.app.models import User, ChatMessage, GameRoom, Game, ModerationAction
from backend.app.services.auth import require_admin
from backend.app.services.moderation import refresh_moderation_status

router = APIRouter(prefix="/admin", tags=["admin"])


class RestrictRequest(BaseModel):
    duration_minutes: int
    reason: str


class BlockRequest(BaseModel):
    reason: str


class WarningRequest(BaseModel):
    reason: str


class UnrestrictRequest(BaseModel):
    reason: str = "Manual restriction lift by admin"


class GameCreateAdmin(BaseModel):
    name: str
    description: str
    image_url: str
    game_type: str
    min_players: int
    max_players: int


class GameUpdateAdmin(BaseModel):
    name: str = None
    description: str = None
    image_url: str = None
    game_type: str = None
    min_players: int = None
    max_players: int = None
    is_active: bool = None


@router.get("/dashboard")
def get_admin_dashboard(
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    # Core Counts
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.account_status == "ACTIVE").count()
    restricted_users = db.query(User).filter(User.account_status == "RESTRICTED").count()
    blocked_users = db.query(User).filter(User.account_status == "BLOCKED").count()

    total_messages = db.query(ChatMessage).count()
    toxic_messages = db.query(ChatMessage).filter(ChatMessage.status == "Toxic").count()
    safe_messages = total_messages - toxic_messages

    user_message_counts = db.query(
        ChatMessage.user_id,
        func.count(ChatMessage.id).label("total_messages"),
        func.sum(case((ChatMessage.status == "Toxic", 1), else_=0)).label("toxic_messages")
    ).group_by(ChatMessage.user_id).all()
    attention_users = []
    users_by_id = {user.id: user for user in db.query(User).all()}
    for user_id, user_total, user_toxic in user_message_counts:
        user = users_by_id.get(user_id)
        if not user:
            continue
        total = int(user_total or 0)
        toxic = int(user_toxic or 0)
        attention_users.append({
            "id": user.id,
            "username": user.username,
            "total_messages": total,
            "toxic_msg_count": toxic,
            "toxicity_rate": round((toxic / total) * 100, 1) if total else 0,
            "account_status": user.account_status
        })
    attention_users.sort(key=lambda user: (user["toxicity_rate"], user["toxic_msg_count"]), reverse=True)

    active_rooms = db.query(GameRoom).filter(GameRoom.room_status == "ACTIVE").count()
    total_games = db.query(Game).count()

    # Toxicity Category Distribution
    categories = db.query(ChatMessage.prediction, func.count(ChatMessage.id)).filter(
        ChatMessage.status == "Toxic"
    ).group_by(ChatMessage.prediction).all()

    cat_distribution = {cat: count for cat, count in categories}

    moderation_distribution_query = db.query(
        ModerationAction.action_type,
        func.count(ModerationAction.id)
    ).group_by(ModerationAction.action_type).all()
    moderation_distribution = {
        action_type: count for action_type, count in moderation_distribution_query
    }

    # Top Toxic Users: ordered by user warnings count
    toxic_users_query = db.query(User.username, User.warning_count).filter(User.warning_count > 0).order_by(User.warning_count.desc()).limit(5).all()
    top_toxic_users = [{"username": u.username, "warnings": u.warning_count} for u in toxic_users_query]

    # Build the requested calendar range before merging database aggregates.
    today = datetime.now(timezone.utc).date()
    try:
        range_end = datetime.fromisoformat(end_date).date() if end_date else today
        range_start = datetime.fromisoformat(start_date).date() if start_date else range_end - timedelta(days=6)
    except ValueError:
        range_end = today
        range_start = today - timedelta(days=6)
    if range_start > range_end:
        range_start, range_end = range_end, range_start
    range_start_dt = datetime.combine(range_start, datetime.min.time(), tzinfo=timezone.utc)
    range_end_dt = datetime.combine(range_end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    timeline_query = db.query(
    func.date(ChatMessage.created_at).label("day"),
    func.count(ChatMessage.id).label("total"),
    func.sum(
        case(
            (ChatMessage.status == "Toxic", 1),
            else_=0
        )
    ).label("toxic")
).filter(
    ChatMessage.created_at >= range_start_dt,
    ChatMessage.created_at < range_end_dt
).group_by(
    func.date(ChatMessage.created_at)
).order_by(
    func.date(ChatMessage.created_at)
).all()
    timeline = []
    timeline_by_day = {str(day): (int(total or 0), int(toxic or 0)) for day, total, toxic in timeline_query}
    day_count = (range_end - range_start).days + 1
    for day_offset in range(day_count):
        day_value = range_start + timedelta(days=day_offset)
        day_str = day_value.isoformat()
        total, toxic_count = timeline_by_day.get(day_str, (0, 0))
        timeline.append({
            "date": day_str,
            "total": total,
            "toxic": toxic_count,
            "toxicity_rate": round((toxic_count / total) * 100, 1) if total else 0,
            "safe": total - toxic_count
        })

    today_start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    week_start = today_start - timedelta(days=6)
    today_messages = db.query(ChatMessage).filter(ChatMessage.created_at >= today_start).count()
    today_toxic_messages = db.query(ChatMessage).filter(
        ChatMessage.created_at >= today_start,
        ChatMessage.status == "Toxic"
    ).count()
    week_messages = db.query(ChatMessage).filter(ChatMessage.created_at >= week_start).count()
    week_users = db.query(User).filter(User.created_at >= week_start).count()
    recent_messages = db.query(ChatMessage).filter(
        ChatMessage.status == "Toxic"
    ).order_by(ChatMessage.created_at.desc()).limit(100).all()
    recent_toxic_activity = [{
        "id": message.id,
        "username": message.user.username if message.user else "Deleted User",
        "message": message.message,
        "prediction": message.prediction,
        "confidence": message.confidence,
        "created_at": message.created_at,
        "game_name": message.game.name if message.game else None,
        "room_name": message.room.room_name if message.room else None
    } for message in recent_messages]

    return {
        "fetched_at": datetime.now(timezone.utc),
        "stats": {
            "total_users": total_users,
            "active_users": active_users,
            "restricted_users": restricted_users,
            "blocked_users": blocked_users,
            "total_messages": total_messages,
            "toxic_messages": toxic_messages,
            "safe_messages": safe_messages,
            "total_games": total_games,
            "active_rooms": active_rooms,
            "today_messages": today_messages,
            "today_toxic_messages": today_toxic_messages,
            "week_messages": week_messages,
            "week_users": week_users
        },
        "charts": {
            "categories": cat_distribution,
            "top_toxic_users": top_toxic_users,
            "timeline": timeline,
            "moderation_actions": moderation_distribution
        },
        "attention_users": attention_users[:10],
        "recent_toxic_activity": recent_toxic_activity
    }


@router.get("/users")
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    users = db.query(User).all()
    result = []
    for u in users:
        refresh_moderation_status(u, db)
        # Count user's toxic messages
        toxic_count = db.query(ChatMessage).filter(
            ChatMessage.user_id == u.id,
            ChatMessage.status == "Toxic"
        ).count()
        # Count user's total messages
        total_count = db.query(ChatMessage).filter(
            ChatMessage.user_id == u.id
        ).count()
        toxicity_rate = 0
        if total_count > 0:
            try:
                toxicity_rate = round((toxic_count / total_count) * 100, 1)
            except Exception:
                toxicity_rate = 0

        result.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "account_status": u.account_status,
            "warning_count": u.warning_count,
            "toxic_msg_count": toxic_count,
            "total_messages": total_count,
            "toxicity_rate": toxicity_rate,
            "created_at": u.created_at
        })
    return result


@router.get("/users/{user_id}")
def get_user_details(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    refresh_moderation_status(user, db)

    # Get user messages
    chats = db.query(ChatMessage).filter(ChatMessage.user_id == user_id).order_by(ChatMessage.created_at.desc()).limit(20).all()
    chats_list = [{
        "id": c.id,
        "message": c.message,
        "prediction": c.prediction,
        "status": c.status,
        "confidence": c.confidence,
        "created_at": c.created_at
    } for c in chats]

    # Get user moderation history
    history = db.query(ModerationAction).filter(ModerationAction.user_id == user_id).order_by(ModerationAction.created_at.desc()).all()
    history_list = [{
        "id": h.id,
        "action_type": h.action_type,
        "reason": h.reason,
        "restriction_start": h.restriction_start,
        "restriction_end": h.restriction_end,
        "created_at": h.created_at
    } for h in history]

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "account_status": user.account_status,
            "warning_count": user.warning_count,
            "created_at": user.created_at
        },
        "chat_history": chats_list,
        "moderation_history": history_list
    }


@router.post("/users/{user_id}/restrict")
@router.patch("/users/{user_id}/restrict")
def restrict_user(
    user_id: int,
    data: RestrictRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    if user.account_status == "BLOCKED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use unblock to restore a blocked user")

    user.account_status = "RESTRICTED"
    db.add(user)

    if data.duration_minutes <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duration must be greater than zero")

    now = datetime.now(timezone.utc)
    restrict_end = now + timedelta(minutes=data.duration_minutes)

    action = ModerationAction(
        user_id=user_id,
        admin_id=admin.id,
        action_type="RESTRICT",
        reason=data.reason,
        restriction_start=now,
        restriction_end=restrict_end
    )
    db.add(action)
    db.commit()
    return {"message": f"User restricted successfully until {restrict_end.isoformat()}"}


@router.post("/users/{user_id}/unrestrict")
@router.patch("/users/{user_id}/unrestrict")
def unrestrict_user(
    user_id: int,
    data: UnrestrictRequest = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    if user.account_status == "BLOCKED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Blocked users must be unblocked explicitly")

    user.account_status = "ACTIVE"
    db.add(user)

    action = ModerationAction(
        user_id=user_id,
        admin_id=admin.id,
        action_type="UNRESTRICT",
        reason=data.reason if data else "Manual restriction lift by admin"
    )
    db.add(action)
    db.commit()
    return {"message": "User restriction removed successfully"}


@router.post("/users/{user_id}/block")
@router.patch("/users/{user_id}/block")
def block_user(
    user_id: int,
    data: BlockRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user.account_status = "BLOCKED"
    db.add(user)

    action = ModerationAction(
        user_id=user_id,
        admin_id=admin.id,
        action_type="BLOCK",
        reason=data.reason
    )
    db.add(action)
    db.commit()
    return {"message": "User blocked successfully"}


@router.post("/users/{user_id}/unblock")
@router.patch("/users/{user_id}/unblock")
def unblock_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user.account_status = "ACTIVE"
    db.add(user)

    action = ModerationAction(
        user_id=user_id,
        admin_id=admin.id,
        action_type="UNBLOCK",
        reason="Manual unblock by admin"
    )
    db.add(action)
    db.commit()
    return {"message": "User unblocked successfully"}


@router.post("/users/{user_id}/warn")
def warn_user(
    user_id: int,
    data: WarningRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.warning_count += 1
    db.add(user)
    db.add(ModerationAction(
        user_id=user_id,
        admin_id=admin.id,
        action_type="WARNING",
        reason=data.reason,
    ))
    db.commit()
    return {"message": "Warning recorded successfully", "warning_count": user.warning_count}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}


@router.get("/flagged-messages")
def list_flagged_messages(
    user_id: int = None,
    game_id: int = None,
    prediction: str = None,
    start_date: str = None,
    end_date: str = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    query = db.query(ChatMessage).filter(ChatMessage.status == "Toxic")

    if user_id:
        query = query.filter(ChatMessage.user_id == user_id)
    if game_id:
        query = query.filter(ChatMessage.game_id == game_id)
    if prediction:
        query = query.filter(ChatMessage.prediction == prediction)
    from datetime import datetime
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            query = query.filter(ChatMessage.created_at >= sd)
        except Exception:
            pass
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            query = query.filter(ChatMessage.created_at <= ed)
        except Exception:
            pass

    messages = query.order_by(ChatMessage.created_at.desc()).offset(offset).limit(limit).all()
    result = []
    for m in messages:
        result.append({
            "id": m.id,
            "user_id": m.user_id,
            "game_id": m.game_id,
            "room_id": m.room_id,
            "message": m.message,
            "username": m.user.username if m.user else "Deleted User",
            "game_name": m.game.name if m.game else None,
            "room_name": m.room.room_name if m.room else None,
            "prediction": m.prediction,
            "confidence": m.confidence,
            "selected_model": m.selected_model,
            "created_at": m.created_at
        })
    return result


@router.get("/moderation")
def list_moderation_actions(limit: int = 50, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    actions = db.query(ModerationAction).order_by(ModerationAction.created_at.desc()).limit(limit).all()
    result = []
    for a in actions:
        result.append({
            "id": a.id,
            "user_id": a.user_id,
            "user": a.user.username if a.user else "Deleted User",
            "admin_id": a.admin_id,
            "admin": a.admin.username if a.admin else None,
            "action_type": a.action_type,
            "reason": a.reason,
            "restriction_start": a.restriction_start,
            "restriction_end": a.restriction_end,
            "created_at": a.created_at,
            "source": "ADMIN" if a.admin_id else "SYSTEM",
        })
    return result


@router.post("/games")
def add_game(
    data: GameCreateAdmin,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    existing = db.query(Game).filter(Game.name == data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Game with this name already exists"
        )

    new_game = Game(
        name=data.name,
        description=data.description,
        image_url=data.image_url,
        game_type=data.game_type,
        min_players=data.min_players,
        max_players=data.max_players,
        is_active=True
    )
    db.add(new_game)
    db.commit()
    db.refresh(new_game)
    return new_game


@router.patch("/games/{game_id}")
def edit_game(
    game_id: int,
    data: GameUpdateAdmin,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found"
        )

    for key, value in data.dict(exclude_unset=True).items():
        setattr(game, key, value)

    db.commit()
    db.refresh(game)
    return game


@router.delete("/games/{game_id}")
def delete_game(
    game_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found"
        )

    db.delete(game)
    db.commit()
    return {"message": "Game deleted successfully"}
