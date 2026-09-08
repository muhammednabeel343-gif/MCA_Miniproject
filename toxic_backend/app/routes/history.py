from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import ChatMessage


router = APIRouter()


@router.get("/history")
def get_history(db: Session = Depends(get_db)):
    chats = (
        db.query(ChatMessage)
        .order_by(ChatMessage.created_at.desc())
        .all()
    )

    return chats