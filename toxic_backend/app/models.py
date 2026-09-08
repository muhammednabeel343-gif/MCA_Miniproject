from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="USER", nullable=False)  # USER, ADMIN
    account_status = Column(String, default="ACTIVE", nullable=False)  # ACTIVE, RESTRICTED, BLOCKED
    warning_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationships
    messages = relationship("ChatMessage", back_populates="user")
    moderation_actions = relationship("ModerationAction", foreign_keys="[ModerationAction.user_id]", back_populates="user")
    created_rooms = relationship("GameRoom", back_populates="creator")
    room_participations = relationship("GameRoomPlayer", back_populates="user")


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    game_type = Column(String, nullable=True)  # e.g., "board", "arcade"
    min_players = Column(Integer, default=2, nullable=False)
    max_players = Column(Integer, default=2, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    rooms = relationship("GameRoom", back_populates="game")
    messages = relationship("ChatMessage", back_populates="game")
    sessions = relationship("GameSession", back_populates="game")


class GameRoom(Base):
    __tablename__ = "game_rooms"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    room_name = Column(String, nullable=False)
    room_status = Column(String, default="WAITING", nullable=False)  # WAITING, ACTIVE, FINISHED
    max_players = Column(Integer, default=2, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    game = relationship("Game", back_populates="rooms")
    creator = relationship("User", back_populates="created_rooms")
    players = relationship("GameRoomPlayer", back_populates="room", cascade="all, delete-orphan")
    messages = relationship("ChatMessage", back_populates="room", cascade="all, delete-orphan")
    sessions = relationship("GameSession", back_populates="room", cascade="all, delete-orphan")


class GameRoomPlayer(Base):
    __tablename__ = "game_room_players"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("game_rooms.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    left_at = Column(DateTime(timezone=True), nullable=True)
    player_status = Column(String, default="JOINED")  # JOINED, LEFT, READY

    # Relationships
    room = relationship("GameRoom", back_populates="players")
    user = relationship("User", back_populates="room_participations")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=True)
    room_id = Column(Integer, ForeignKey("game_rooms.id"), nullable=True)

    message = Column(String, nullable=False)
    prediction = Column(String, nullable=False)
    status = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    selected_model = Column(String, nullable=False)

    # New additions
    logistic_regression_prediction = Column(String, nullable=True)
    logistic_regression_confidence = Column(Float, nullable=True)
    svm_prediction = Column(String, nullable=True)
    svm_confidence = Column(Float, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="messages")
    game = relationship("Game", back_populates="messages")
    room = relationship("GameRoom", back_populates="messages")


class ModerationAction(Base):
    __tablename__ = "moderation_actions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action_type = Column(String, nullable=False)  # WARNING, RESTRICT, UNRESTRICT, BLOCK, UNBLOCK
    reason = Column(String, nullable=True)
    restriction_start = Column(DateTime(timezone=True), nullable=True)
    restriction_end = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="moderation_actions")
    admin = relationship("User", foreign_keys=[admin_id])


class GameSession(Base):
    __tablename__ = "game_sessions"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    room_id = Column(Integer, ForeignKey("game_rooms.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    winner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_status = Column(String, default="WAITING", nullable=False)  # WAITING, ACTIVE, FINISHED

    # Relationships
    game = relationship("Game", back_populates="sessions")
    room = relationship("GameRoom", back_populates="sessions")
    winner = relationship("User")
