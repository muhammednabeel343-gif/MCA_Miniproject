import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import (
    User,
    ChatMessage as ChatMessageDB,
    GameRoom,
    ModerationAction,
    GameRoomPlayer,
)
from app.services.auth import decode_access_token, require_active_user
from app.services.moderation import refresh_moderation_status
from app.services.model_service import predict_message


logger = logging.getLogger("chat_ws")

router = APIRouter(tags=["chat"])


# ============================================================
# WebSocket Connection Manager
# ============================================================

class ConnectionManager:

    def __init__(self):
        # room_id -> list of active WebSocket connections
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, room_id: int, websocket: WebSocket):
        """
        Accept and register a WebSocket connection.
        """
        await websocket.accept()

        if room_id not in self.active_connections:
            self.active_connections[room_id] = []

        self.active_connections[room_id].append(websocket)

        logger.info(
            f"WebSocket registered successfully: room_id={room_id}"
        )

    def disconnect(self, room_id: int, websocket: WebSocket):
        """
        Remove a WebSocket connection from its room.
        """
        if room_id not in self.active_connections:
            return

        if websocket in self.active_connections[room_id]:
            self.active_connections[room_id].remove(websocket)

        if not self.active_connections[room_id]:
            del self.active_connections[room_id]

        logger.info(
            f"WebSocket disconnected: room_id={room_id}"
        )

    async def broadcast_to_room(self, room_id: int, message: dict):
        """
        Send a message to every connected user in the room.
        """
        if room_id not in self.active_connections:
            return

        disconnected_connections = []

        for connection in list(self.active_connections[room_id]):
            try:
                await connection.send_json(message)

            except Exception as e:
                logger.warning(
                    f"Removing disconnected WebSocket: {repr(e)}"
                )
                disconnected_connections.append(connection)

        for connection in disconnected_connections:
            self.disconnect(room_id, connection)


manager = ConnectionManager()


# ============================================================
# WebSocket Handler Endpoint
# ============================================================

@router.websocket("/ws/chat/{room_id}")
async def websocket_chat_endpoint(
    room_id: int,
    websocket: WebSocket,
    token: str = Query(None)
):

    print(
        f"WEBSOCKET HIT: room_id={room_id}, "
        f"token_present={bool(token)}"
    )

    logger.info(
        f"WEBSOCKET HIT: room_id={room_id}, "
        f"token_present={bool(token)}"
    )

    db = SessionLocal()
    user = None
    connected = False

    try:

        # ====================================================
        # ACCEPT WEBSOCKET CONNECTION
        # ====================================================
        #
        # Accept immediately so the WebSocket handshake is
        # completed before authentication/room validation.
        #
        await websocket.accept()

        logger.info(
            f"WebSocket handshake accepted: room_id={room_id}"
        )

        # ====================================================
        # VALIDATE TOKEN
        # ====================================================

        if not token:
            logger.warning(
                f"WebSocket rejected: Token required "
                f"(room_id={room_id})"
            )

            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Token required"
            )
            return

        try:
            payload = decode_access_token(token)

        except Exception as e:
            logger.error(
                f"Token decode error: {repr(e)}"
            )

            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Invalid token"
            )
            return

        if not payload or "sub" not in payload:

            logger.warning(
                f"WebSocket rejected: Invalid token "
                f"(room_id={room_id})"
            )

            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Invalid token"
            )
            return

        # ====================================================
        # FIND USER
        # ====================================================

        username = payload["sub"]

        user = (
            db.query(User)
            .filter(User.username == username)
            .first()
        )

        if not user:

            logger.warning(
                f"WebSocket rejected: User not found "
                f"(username={username}, room_id={room_id})"
            )

            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="User not found"
            )
            return

        # ====================================================
        # CHECK ROOM
        # ====================================================

        room = (
            db.query(GameRoom)
            .filter(GameRoom.id == room_id)
            .first()
        )

        if not room:

            logger.warning(
                f"WebSocket rejected: Room {room_id} "
                f"does not exist"
            )

            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Room does not exist"
            )
            return

        logger.info(
            f"WebSocket validated: "
            f"user={user.username}, room={room_id}"
        )

        # ====================================================
        # REGISTER CONNECTION
        # ====================================================

        #
        # NOTE:
        # manager.connect() no longer calls accept()
        # because the connection was already accepted above.
        #
        if room_id not in manager.active_connections:
            manager.active_connections[room_id] = []

        manager.active_connections[room_id].append(websocket)

        connected = True

        logger.info(
            f"WebSocket connected successfully: "
            f"user={user.username}, room={room_id}"
        )

        # ====================================================
        # BROADCAST JOIN NOTIFICATION
        # ====================================================

        await manager.broadcast_to_room(
            room_id,
            {
                "type": "system",
                "message": f"{user.username} entered the room.",
                "username": "System",
                "timestamp": datetime.now(
                    timezone.utc
                ).isoformat(),
            }
        )

        # ====================================================
        # REFRESH MODERATION STATUS
        # ====================================================

        refresh_moderation_status(user, db)

        if user.account_status == "BLOCKED":

            await websocket.send_json(
                {
                    "type": "system",
                    "message": (
                        "Your account is BLOCKED. "
                        "Chat and gameplay are unavailable."
                    ),
                    "status": "BLOCKED",
                    "username": "System",
                    "timestamp": datetime.now(
                        timezone.utc
                    ).isoformat(),
                }
            )

        # ====================================================
        # MAIN WEBSOCKET LOOP
        # ====================================================

        while True:

            data = await websocket.receive_text()

            logger.info(
                f"WebSocket message received: "
                f"user={user.username}, room={room_id}"
            )

            try:
                message_data = json.loads(data)

            except json.JSONDecodeError:

                logger.warning(
                    f"Invalid JSON received from "
                    f"user={user.username}"
                )

                await websocket.send_json(
                    {
                        "type": "system",
                        "message": "Invalid WebSocket message.",
                        "username": "System",
                        "timestamp": datetime.now(
                            timezone.utc
                        ).isoformat(),
                    }
                )

                continue

            msg_type = message_data.get("type", "chat")

            # =================================================
            # REFRESH MODERATION STATUS
            # =================================================

            refresh_moderation_status(user, db)

            # =================================================
            # GAME MOVE
            # =================================================

            if msg_type == "game_move":

                if user.account_status == "BLOCKED":

                    await websocket.send_json(
                        {
                            "type": "system",
                            "message": (
                                "Blocked users cannot make "
                                "game moves."
                            ),
                            "status": "BLOCKED",
                            "username": "System",
                            "timestamp": datetime.now(
                                timezone.utc
                            ).isoformat(),
                        }
                    )

                    continue

                await manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "game_move",
                        "sender": user.username,
                        "state": message_data.get("state"),
                        "timestamp": datetime.now(
                            timezone.utc
                        ).isoformat(),
                    }
                )

                continue

            # =================================================
            # CHAT
            # =================================================

            message_text = (
                message_data.get("message", "")
                .strip()
            )

            if not message_text:
                continue

            # =================================================
            # BLOCKED USER
            # =================================================

            if user.account_status == "BLOCKED":

                await websocket.send_json(
                    {
                        "type": "system",
                        "message": (
                            "Blocked users cannot send "
                            "chat messages."
                        ),
                        "status": "BLOCKED",
                        "username": "System",
                        "timestamp": datetime.now(
                            timezone.utc
                        ).isoformat(),
                    }
                )

                continue

            # =================================================
            # RESTRICTED USER
            # =================================================

            if user.account_status == "RESTRICTED":

                await websocket.send_json(
                    {
                        "type": "system",
                        "message": (
                            "You are currently restricted "
                            "from sending chat messages."
                        ),
                        "status": "RESTRICTED",
                        "username": "System",
                        "timestamp": datetime.now(
                            timezone.utc
                        ).isoformat(),
                    }
                )

                continue

            # =================================================
            # ML PREDICTION
            # =================================================

            logger.info(
                f"Running toxicity prediction for "
                f"user={user.username}, room={room_id}"
            )

            prediction_result = predict_message(
                message_text
            )

            status_label = prediction_result["status"]

            # =================================================
            # SAVE MESSAGE TO DATABASE
            # =================================================

            chat_record = ChatMessageDB(
                user_id=user.id,
                game_id=room.game_id,
                room_id=room_id,
                message=message_text,
                prediction=prediction_result["prediction"],
                status=status_label,
                confidence=prediction_result["confidence"],
                selected_model=prediction_result[
                    "selected_model"
                ],
                logistic_regression_prediction=(
                    prediction_result[
                        "logistic_regression_prediction"
                    ]
                ),
                logistic_regression_confidence=(
                    prediction_result[
                        "logistic_regression_confidence"
                    ]
                ),
                svm_prediction=prediction_result[
                    "svm_prediction"
                ],
                svm_confidence=prediction_result[
                    "svm_confidence"
                ],
            )

            db.add(chat_record)
            db.commit()
            db.refresh(chat_record)

            # =================================================
            # MODERATION VIOLATION CHECK
            # =================================================

            is_toxic = (
                status_label == "Toxic"
            )

            warning_triggered = False
            restriction_triggered = False

            if is_toxic:

                user.warning_count += 1

                db.add(user)
                db.commit()

                # =============================================
                # FIRST VIOLATION -> WARNING
                # =============================================

                if user.warning_count == 1:

                    mod_action = ModerationAction(
                        user_id=user.id,
                        action_type="WARNING",
                        reason=(
                            f"Toxic message: "
                            f"'{message_text}'"
                        ),
                    )

                    db.add(mod_action)
                    db.commit()

                    warning_triggered = True

                    logger.info(
                        f"Warning issued to "
                        f"user={user.username}"
                    )

                # =============================================
                # REPEATED VIOLATION -> RESTRICT
                # =============================================

                else:

                    user.account_status = "RESTRICTED"

                    db.add(user)

                    now = datetime.now(
                        timezone.utc
                    )

                    restrict_end = (
                        now + timedelta(minutes=5)
                    )

                    mod_action = ModerationAction(
                        user_id=user.id,
                        action_type="RESTRICT",
                        reason=(
                            f"Repeated toxicity: "
                            f"'{message_text}'"
                        ),
                        restriction_start=now,
                        restriction_end=restrict_end,
                    )

                    db.add(mod_action)
                    db.commit()

                    restriction_triggered = True

                    logger.info(
                        f"User restricted: "
                        f"user={user.username}, "
                        f"until={restrict_end}"
                    )

            # =================================================
            # BROADCAST CHAT MESSAGE
            # =================================================

            await manager.broadcast_to_room(
                room_id,
                {
                    "type": "chat",
                    "id": chat_record.id,
                    "user_id": user.id,
                    "username": user.username,
                    "message": message_text,
                    "status": status_label,
                    "prediction": prediction_result[
                        "prediction"
                    ],
                    "confidence": prediction_result[
                        "confidence"
                    ],
                    "warning_triggered": (
                        warning_triggered
                    ),
                    "restriction_triggered": (
                        restriction_triggered
                    ),
                    "timestamp": (
                        chat_record.created_at.isoformat()
                    ),
                }
            )

    # ========================================================
    # NORMAL DISCONNECT
    # ========================================================

    except WebSocketDisconnect:

        logger.info(
            f"WebSocketDisconnect: "
            f"user={user.username if user else 'unknown'}, "
            f"room={room_id}"
        )

        if connected:
            manager.disconnect(
                room_id,
                websocket
            )

        if user:

            await manager.broadcast_to_room(
                room_id,
                {
                    "type": "system",
                    "message": (
                        f"{user.username} left the room."
                    ),
                    "username": "System",
                    "timestamp": datetime.now(
                        timezone.utc
                    ).isoformat(),
                }
            )

    # ========================================================
    # OTHER WEBSOCKET ERRORS
    # ========================================================

    except Exception as e:

        logger.exception(
            f"WebSocket error in endpoint: "
            f"room={room_id}, "
            f"user={user.username if user else 'unknown'}"
        )

        if connected:
            manager.disconnect(
                room_id,
                websocket
            )

    # ========================================================
    # CLEANUP
    # ========================================================

    finally:

        db.close()

        logger.info(
            f"WebSocket handler finished: "
            f"room={room_id}, "
            f"user={user.username if user else 'unknown'}"
        )


# ============================================================
# User Chat History API Routes
# ============================================================

@router.get("/history/me")
def get_my_chat_history(
    game_id: int = None,
    status_filter: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    query = (
        db.query(ChatMessageDB)
        .filter(
            ChatMessageDB.user_id == current_user.id
        )
    )

    if game_id:
        query = query.filter(
            ChatMessageDB.game_id == game_id
        )

    if status_filter:
        query = query.filter(
            ChatMessageDB.status == status_filter
        )

    chats = (
        query
        .order_by(
            ChatMessageDB.created_at.desc()
        )
        .all()
    )

    result = []

    for c in chats:

        result.append(
            {
                "id": c.id,
                "message": c.message,
                "prediction": c.prediction,
                "status": c.status,
                "confidence": c.confidence,
                "selected_model": c.selected_model,
                "game_name": (
                    c.game.name
                    if c.game
                    else None
                ),
                "room_name": (
                    c.room.room_name
                    if c.room
                    else None
                ),
                "created_at": c.created_at,
            }
        )

    return result


@router.get("/history/room/{room_id}")
def get_room_chat_history(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):

    chats = (
        db.query(ChatMessageDB)
        .filter(
            ChatMessageDB.room_id == room_id
        )
        .order_by(
            ChatMessageDB.created_at.asc()
        )
        .all()
    )

    result = []

    for c in chats:

        result.append(
            {
                "id": c.id,
                "user_id": c.user_id,
                "username": (
                    c.user.username
                    if c.user
                    else "Deleted User"
                ),
                "message": c.message,
                "status": c.status,
                "prediction": c.prediction,
                "confidence": c.confidence,
                "timestamp": (
                    c.created_at.isoformat()
                ),
            }
        )

    return result