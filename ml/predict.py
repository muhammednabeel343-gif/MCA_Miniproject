from fastapi import APIRouter
from pydantic import BaseModel
from backend.app.services.model_service import predict_message

router = APIRouter()


class ChatMessage(BaseModel):
    message: str


@router.post("/predict")
def predict_toxicity(data: ChatMessage):
    result = predict_message(data.message)

    return {
        "message": data.message,
        **result
    }