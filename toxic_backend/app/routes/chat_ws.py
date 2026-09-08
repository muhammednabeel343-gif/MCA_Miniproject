import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import User, ChatMessage as ChatMessageDB, GameRoom, ModerationAction, GameRoomPlayer
from app.services.auth import decode_access_token, require_active_user
from app.services.moderation import refresh_moderation_status
from app.services.model_service import predict_message

logger = logging.getLogger("chat_ws")
router = APIRouter(tags=["chat"])


# -----------------------------
# WebSocket Connection Manager
# -----------------------------
class ConnectionManager:
    def __init__(self):
        # Maps room_id -> list of active WebSocket structures
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, room_id: int, websocket: WebSocket):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, room_id: int, websocket: WebSocket):
        if room_id in self.active_connections:
            if websocket in self.active_connections[room_id]:
                self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast_to_room(self, room_id: int, message: dict):
                    if room_id not in self.active_connections:
                        return

                    disconnected_connections = []

                    for connection in list(self.active_connections[room_id]):
                        try:
                            await connection.send_json(message)
                        except Exception as e:
                            logger.warning(f"Removing disconnected WebSocket: {e}")
                            disconnected_connections.append(connection)

                    for connection in disconnected_connections:
                        self.disconnect(room_id, connection)


manager = ConnectionManager()


# -----------------------------
# WebSocket Handler Endpoint
# -----------------------------
@router.websocket("/ws/chat/{room_id}")
async def websocket_chat_endpoint(room_id: int, websocket: WebSocket, token: str = Query(None)):
    print(f"WEBSOCKET HIT: room_id={room_id}, token_present={bool(token)}")

    db = SessionLocal()
    user = None

    try:
        # Validate connection token
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token required")
            return

        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return

        user = db.query(User).filter(User.username == payload["sub"]).first()
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found")
            return

        # Check room validity
        room = db.query(GameRoom).filter(GameRoom.id == room_id).first()
        if not room:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Room does not exist")
            return

        # Register connection
        await manager.connect(room_id, websocket)

        # Broadcast join notification
        await manager.broadcast_to_room(room_id, {
            "type": "system",
            "message": f"{user.username} entered the room.",
            "username": "System",
            "timestamp": datetime.utcnow().isoformat()
        })

        refresh_moderation_status(user, db)
        if user.account_status == "BLOCKED":
            await websocket.send_json({
                "type": "system",
                "message": "Your account is BLOCKED. Chat and gameplay are unavailable.",
                "status": "BLOCKED",
                "username": "System",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        while True:
            # Await input frame
            data = await websocket.receive_text()
            message_data = json.loads(data)

            msg_type = message_data.get("type", "chat")

            refresh_moderation_status(user, db)

            if msg_type == "game_move":
                if user.account_status == "BLOCKED":
                    await websocket.send_json({
                        "type": "system",
                        "message": "Blocked users cannot make game moves.",
                        "status": "BLOCKED",
                        "username": "System",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    continue

                await manager.broadcast_to_room(room_id, {
                    "type": "game_move",
                    "sender": user.username,
                    "state": message_data.get("state"),
                    "timestamp": datetime.utcnow().isoformat()
                })
                continue

            # Default chat handler
            message_text = message_data.get("message", "").strip()
            if not message_text:
                continue

            if user.account_status == "BLOCKED":
                await websocket.send_json({
                    "type": "system",
                    "message": "Blocked users cannot send chat messages.",
                    "status": "BLOCKED",
                    "username": "System",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                continue

            if user.account_status == "RESTRICTED":
                await websocket.send_json({
                    "type": "system",
                    "message": "You are currently restricted from sending chat messages.",
                    "status": "RESTRICTED",
                    "username": "System",
                    "timestamp": datetime.utcnow().isoformat()
                })
                continue

            # Evaluate message classification using existing ML service
            prediction_result = predict_message(message_text)
            status_label = prediction_result["status"]  # Safe or Toxic

            # Record to databases
            chat_record = ChatMessageDB(
                user_id=user.id,
                game_id=room.game_id,
                room_id=room_id,
                message=message_text,
                prediction=prediction_result["prediction"],
                status=status_label,
                confidence=prediction_result["confidence"],
                selected_model=prediction_result["selected_model"],
                logistic_regression_prediction=prediction_result["logistic_regression_prediction"],
                logistic_regression_confidence=prediction_result["logistic_regression_confidence"],
                svm_prediction=prediction_result["svm_prediction"],
                svm_confidence=prediction_result["svm_confidence"]
            )
            db.add(chat_record)
            db.commit()
            db.refresh(chat_record)

            # Moderation violation checking
            is_toxic = (status_label == "Toxic")
            warning_triggered = False
            restriction_triggered = False

            if is_toxic:
                user.warning_count += 1
                db.add(user)
                db.commit()

                # Determine penalty
                if user.warning_count == 1:
                    # Issue Warning action
                    mod_action = ModerationAction(
                        user_id=user.id,
                        action_type="WARNING",
                        reason=f"Toxic message: '{message_text}'"
                    )
                    db.add(mod_action)
                    db.commit()
                    warning_triggered = True
                else:
                    # Restrict account for 5 minutes initially
                    user.account_status = "RESTRICTED"
                    db.add(user)
                    
                    now = datetime.now(timezone.utc)
                    restrict_end = now + timedelta(minutes=5)

                    mod_action = ModerationAction(
                        user_id=user.id,
                        action_type="RESTRICT",
                        reason=f"Repeated toxicity: '{message_text}'",
                        restriction_start=now,
                        restriction_end=restrict_end
)
                    db.add(mod_action)
                    db.commit()
                    restriction_triggered = True

            # Broadcast message to room
            await manager.broadcast_to_room(room_id, {
                "type": "chat",
                "id": chat_record.id,
                "user_id": user.id,
                "username": user.username,
                "message": message_text,
                "status": status_label,
                "prediction": prediction_result["prediction"],
                "confidence": prediction_result["confidence"],
                "warning_triggered": warning_triggered,
                "restriction_triggered": restriction_triggered,
                "timestamp": chat_record.created_at.isoformat()
            })

    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)
        if user:
            await manager.broadcast_to_room(room_id, {
                "type": "system",
                "message": f"{user.username} left the room.",
                "username": "System",
                "timestamp": datetime.utcnow().isoformat()
            })
    except Exception as e:
        logger.error(f"WebSocket error in endpoint: {e}")
        manager.disconnect(room_id, websocket)
    finally:
        db.close()


# -----------------------------
# User Chat History API Routes
# -----------------------------
@router.get("/history/me")
def get_my_chat_history(
    game_id: int = None,
    status_filter: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user)
):
    query = db.query(ChatMessageDB).filter(ChatMessageDB.user_id == current_user.id)
    if game_id:
        query = query.filter(ChatMessageDB.game_id == game_id)
    if status_filter:
        query = query.filter(ChatMessageDB.status == status_filter)

    chats = query.order_by(ChatMessageDB.created_at.desc()).all()
    
    result = []
    for c in chats:
        result.append({
            "id": c.id,
            "message": c.message,
            "prediction": c.prediction,
            "status": c.status,
            "confidence": c.confidence,
            "selected_model": c.selected_model,
            "game_name": c.game.name if c.game else None,
            "room_name": c.room.room_name if c.room else None,
            "created_at": c.created_at
        })
    return result


@router.get("/history/room/{room_id}")
def get_room_chat_history(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user)
):
    chats = (
        db.query(ChatMessageDB)
        .filter(ChatMessageDB.room_id == room_id)
        .order_by(ChatMessageDB.created_at.asc())
        .all()
    )

    result = []
    for c in chats:
        result.append({
            "id": c.id,
            "user_id": c.user_id,
            "username": c.user.username if c.user else "Deleted User",
            "message": c.message,
            "status": c.status,
            "prediction": c.prediction,
            "confidence": c.confidence,
            "timestamp": c.created_at.isoformat()
        })
    return result
