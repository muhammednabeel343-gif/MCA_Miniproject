from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..services.model_service import predict_message
from ..database import get_db
from ..models import ChatMessage as ChatMessageDB


router = APIRouter()


class ChatMessageRequest(BaseModel):
    message: str


@router.post("/predict")
def predict_toxicity(
    data: ChatMessageRequest,
    db: Session = Depends(get_db)
):
    # Get prediction from the ML models
    result = predict_message(data.message)

    # Create database record
    chat_record = ChatMessageDB(
        message=data.message,
        prediction=result["prediction"],
        status=result["status"],
        confidence=result["confidence"],
        selected_model=result["selected_model"]
    )

    # Save to Neon PostgreSQL
    db.add(chat_record)
    db.commit()
    db.refresh(chat_record)

    # Return prediction result
    return {
        "message": data.message,
        **result
    }
