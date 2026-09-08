from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import ModerationAction, User


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """Normalize database timestamps before comparing them with UTC now."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def refresh_moderation_status(user: User, db: Session) -> User:
    """Resolve temporary restrictions without ever changing a blocked user."""
    if user.account_status == "BLOCKED":
        return user

    if user.account_status != "RESTRICTED":
        return user

    latest_action = (
        db.query(ModerationAction)
        .filter(
            ModerationAction.user_id == user.id,
            ModerationAction.action_type.in_(("RESTRICT", "UNRESTRICT", "BLOCK", "UNBLOCK")),
        )
        .order_by(ModerationAction.created_at.desc(), ModerationAction.id.desc())
        .first()
    )

    if (
        latest_action
        and latest_action.action_type == "RESTRICT"
        and latest_action.restriction_end
        and utc_now() < as_utc(latest_action.restriction_end)
    ):
        return user

    user.account_status = "ACTIVE"
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def is_blocked(user: User, db: Session) -> bool:
    return refresh_moderation_status(user, db).account_status == "BLOCKED"


def require_game_access(user: User, db: Session) -> User:
    """Allow active and restricted users to play, but reject blocked users."""
    refresh_moderation_status(user, db)
    if user.account_status == "BLOCKED":
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Blocked users cannot create rooms, join rooms, or play games",
        )
    return user
