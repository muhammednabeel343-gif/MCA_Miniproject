from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChatMessage


router = APIRouter()


@router.get("/history")
def get_history(db: Session = Depends(get_db)):
    chats = (
        db.query(ChatMessage)
        .order_by(ChatMessage.created_at.desc())
        .all()
    )

    return chats
