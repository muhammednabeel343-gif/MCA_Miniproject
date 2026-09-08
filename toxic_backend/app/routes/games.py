from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Game, GameRoom, GameRoomPlayer, User
from app.services.auth import require_active_user, require_game_access
from app.routes.chat_ws import manager as ws_manager
import asyncio

router = APIRouter(tags=["rooms"])


class RoomCreate(BaseModel):
    game_id: int
    room_name: str
    max_players: int


@router.get("/games")
def list_games(db: Session = Depends(get_db)):
    return db.query(Game).filter(Game.is_active == True).all()


@router.get("/games/{game_id}")
def get_game(game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).filter(Game.id == game_id, Game.is_active == True).first()
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found"
        )
    return game


@router.post("/rooms")
def create_room(
    data: RoomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_game_access)
):
    game = db.query(Game).filter(Game.id == data.game_id, Game.is_active == True).first()
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found"
        )

    # Clean input
    room_name = data.room_name.strip()
    if not room_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Room name cannot be empty"
        )

    if data.max_players < game.min_players or data.max_players > game.max_players:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Player limits for this game are {game.min_players} to {game.max_players}"
        )

    new_room = GameRoom(
        game_id=data.game_id,
        room_name=room_name,
        max_players=data.max_players,
        room_status="WAITING",
        created_by=current_user.id
    )

    db.add(new_room)
    db.commit()
    db.refresh(new_room)

    # Automatically join creator to room
    join_player = GameRoomPlayer(
        room_id=new_room.id,
        user_id=current_user.id,
        player_status="JOINED"
    )
    db.add(join_player)
    db.commit()

    return {
        "id": new_room.id,
        "room_name": new_room.room_name,
        "room_status": new_room.room_status,
        "max_players": new_room.max_players,
        "game": {
            "id": game.id,
            "name": game.name
        },
        "created_by": current_user.username
    }


@router.get("/rooms")
def list_rooms(game_id: int = None, db: Session = Depends(get_db)):
    query = db.query(GameRoom).filter(GameRoom.room_status != "FINISHED")
    if game_id:
        query = query.filter(GameRoom.game_id == game_id)

    rooms = query.all()
    result = []
    for r in rooms:
        active_players_count = db.query(GameRoomPlayer).filter(
            GameRoomPlayer.room_id == r.id,
            GameRoomPlayer.left_at == None
        ).count()

        result.append({
            "id": r.id,
            "game_id": r.game_id,
            "game_name": r.game.name,
            "room_name": r.room_name,
            "room_status": r.room_status,
            "max_players": r.max_players,
            "active_players": active_players_count,
            "created_at": r.created_at
        })
    return result


@router.get("/rooms/{room_id}")
def get_room(room_id: int, db: Session = Depends(get_db)):
    room = db.query(GameRoom).filter(GameRoom.id == room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found"
        )

    players = db.query(GameRoomPlayer).filter(
        GameRoomPlayer.room_id == room_id,
        GameRoomPlayer.left_at == None
    ).all()

    players_list = []
    for p in players:
        players_list.append({
            "user_id": p.user.id,
            "username": p.user.username,
            "role": p.user.role,
            "player_status": p.player_status
        })

    return {
        "id": room.id,
        "room_name": room.room_name,
        "room_status": room.room_status,
        "max_players": room.max_players,
        "game": {
            "id": room.game.id,
            "name": room.game.name,
            "image_url": room.game.image_url,
            "game_type": room.game.game_type
        },
        "created_by": room.creator.username if room.creator else None,
        "created_at": room.created_at,
        "players": players_list
    }


@router.post("/rooms/{room_id}/join")
def join_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_game_access)
):
    room = db.query(GameRoom).filter(GameRoom.id == room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found"
        )

    if room.room_status == "FINISHED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot join a finished game room"
        )

    # Check if user is already in the room
    existing_player = db.query(GameRoomPlayer).filter(
        GameRoomPlayer.room_id == room_id,
        GameRoomPlayer.user_id == current_user.id,
        GameRoomPlayer.left_at == None
    ).first()

    if existing_player:
        return {"message": "Already inside room", "room_id": room_id}

    # Count current players
    current_count = db.query(GameRoomPlayer).filter(
        GameRoomPlayer.room_id == room_id,
        GameRoomPlayer.left_at == None
    ).count()

    if current_count >= room.max_players:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Room is full"
        )

    # Add player
    join_player = GameRoomPlayer(
        room_id=room_id,
        user_id=current_user.id,
        player_status="JOINED"
    )
    db.add(join_player)

    db.commit()
    return {"message": "Joined room successfully", "room_id": room_id}


@router.post("/rooms/{room_id}/start")
async def start_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_game_access)
):
    room = db.query(GameRoom).filter(GameRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    # Only host can start
    if room.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the host can start the game")

    # Check player count
    current_count = db.query(GameRoomPlayer).filter(
        GameRoomPlayer.room_id == room_id,
        GameRoomPlayer.left_at == None
    ).count()

    if current_count < room.game.min_players:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough players to start the game")

    room.room_status = "ACTIVE"
    room.started_at = datetime.utcnow()
    db.add(room)
    db.commit()

    # Broadcast system message to room via websocket manager (best-effort)
    try:
        await ws_manager.broadcast_to_room(room_id, {
            "type": "system",
            "message": "Host started the game.",
            "username": "System",
            "timestamp": datetime.utcnow().isoformat(),
            "room_status": "ACTIVE"
        })
    except Exception:
        # Do not fail the request if broadcast fails
        pass

    return {"message": "Game started"}


@router.post("/rooms/{room_id}/close")
async def close_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_game_access)
):
    room = db.query(GameRoom).filter(GameRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    # Only host can close
    if room.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the host can close the room")

    room.room_status = "FINISHED"
    room.ended_at = datetime.utcnow()
    db.add(room)
    db.commit()

    try:
        await ws_manager.broadcast_to_room(room_id, {
            "type": "system",
            "message": "Host closed the room. The session has ended.",
            "username": "System",
            "timestamp": datetime.utcnow().isoformat(),
            "room_status": "FINISHED"
        })
    except Exception:
        pass

    return {"message": "Room closed"}


@router.post("/rooms/{room_id}/leave")
def leave_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user)
):
    room = db.query(GameRoom).filter(GameRoom.id == room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found"
        )

    player = db.query(GameRoomPlayer).filter(
        GameRoomPlayer.room_id == room_id,
        GameRoomPlayer.user_id == current_user.id,
        GameRoomPlayer.left_at == None
    ).first()

    if not player:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not in this game room"
        )

    player.left_at = datetime.utcnow()
    player.player_status = "LEFT"
    db.add(player)

    # Check remaining players count
    remaining_count = db.query(GameRoomPlayer).filter(
        GameRoomPlayer.room_id == room_id,
        GameRoomPlayer.left_at == None
    ).count()

    if remaining_count == 0:
        room.room_status = "FINISHED"
        room.ended_at = datetime.utcnow()
        db.add(room)

    db.commit()
    return {"message": "Left room successfully"}
