from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import ModerationAction, User


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """Normalize database timestamps before comparing them with UTC now."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_latest_moderation_action(user: User, db: Session) -> ModerationAction | None:
    return (
        db.query(ModerationAction)
        .filter(
            ModerationAction.user_id == user.id,
            ModerationAction.action_type.in_(("RESTRICT", "UNRESTRICT", "BLOCK", "UNBLOCK")),
        )
        .order_by(ModerationAction.created_at.desc(), ModerationAction.id.desc())
        .first()
    )


def get_active_restriction_end(user: User, db: Session) -> datetime | None:
    latest_action = get_latest_moderation_action(user, db)
    if not latest_action or latest_action.action_type != "RESTRICT":
        return None
    if not latest_action.restriction_end:
        return None
    if utc_now() >= as_utc(latest_action.restriction_end):
        return None
    return as_utc(latest_action.restriction_end)


def refresh_moderation_status(user: User, db: Session) -> User:
    """Keep account status synchronized with the latest moderation action."""
    latest_action = get_latest_moderation_action(user, db)

    if latest_action and latest_action.action_type == "BLOCK":
        if user.account_status != "BLOCKED":
            user.account_status = "BLOCKED"
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    if latest_action and latest_action.action_type == "UNBLOCK":
        if user.account_status != "ACTIVE":
            user.account_status = "ACTIVE"
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    active_restriction_end = get_active_restriction_end(user, db)
    if active_restriction_end is not None:
        if user.account_status != "RESTRICTED":
            user.account_status = "RESTRICTED"
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    if user.account_status != "ACTIVE":
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
