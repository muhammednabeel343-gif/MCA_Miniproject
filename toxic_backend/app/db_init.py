import logging
from sqlalchemy import inspect, text
from .database import engine, Base
from .models import ChatMessage, Game, User
from .services.auth import hash_password

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db_init")


def init_db():
    logger.info("Initializing database...")

    try:
        with engine.connect() as conn:
            logger.info("Checking chat_messages table for columns...")
            try:
                inspector = inspect(conn)
                if inspector.has_table("chat_messages"):
                    column_names = {column["name"] for column in inspector.get_columns("chat_messages")}
                    if "user_id" not in column_names:
                        conn.execute(text("ALTER TABLE chat_messages ADD COLUMN user_id INTEGER"))
                    if "game_id" not in column_names:
                        conn.execute(text("ALTER TABLE chat_messages ADD COLUMN game_id INTEGER"))
                    if "room_id" not in column_names:
                        conn.execute(text("ALTER TABLE chat_messages ADD COLUMN room_id INTEGER"))
                    if "client_message_id" not in column_names:
                        conn.execute(text("ALTER TABLE chat_messages ADD COLUMN client_message_id VARCHAR(64)"))
                    if "logistic_regression_prediction" not in column_names:
                        conn.execute(text("ALTER TABLE chat_messages ADD COLUMN logistic_regression_prediction VARCHAR"))
                    if "logistic_regression_confidence" not in column_names:
                        conn.execute(text("ALTER TABLE chat_messages ADD COLUMN logistic_regression_confidence FLOAT"))
                    if "svm_prediction" not in column_names:
                        conn.execute(text("ALTER TABLE chat_messages ADD COLUMN svm_prediction VARCHAR"))
                    if "svm_confidence" not in column_names:
                        conn.execute(text("ALTER TABLE chat_messages ADD COLUMN svm_confidence FLOAT"))
                    conn.commit()
            except Exception as exc:
                logger.warning(f"Could not upgrade chat_messages schema: {exc}")
    except Exception as exc:
        logger.warning(f"Database connection not available during startup; continuing with SQLite fallback or in-memory mode: {exc}")

    # 2. Create other tables
    logger.info("Creating remaining tables...")
    try:
        Base.metadata.create_all(bind=engine)
        for index in ChatMessage.__table__.indexes:
            if index.name == "uq_chat_messages_user_room_client_id":
                index.create(bind=engine, checkfirst=True)
    except Exception as exc:
        logger.warning(f"Could not create database tables: {exc}")

    # 3. Seed games and users
    from .database import SessionLocal
    db = SessionLocal()
    try:
        games_to_seed = [
            {
                "name": "Chess",
                "description": "Strategic board game",
                "image_url": "Chess",
                "game_type": "board",
                "min_players": 2,
                "max_players": 2,
                "is_active": True
            },
            {
                "name": "Ludo",
                "description": "Classic dice-based board game",
                "image_url": "Ludo",
                "game_type": "board",
                "min_players": 2,
                "max_players": 4,
                "is_active": True
            },
            {
                "name": "Snakes and Ladders",
                "description": "Turn-based board game",
                "image_url": "Snakes",
                "game_type": "board",
                "min_players": 2,
                "max_players": 4,
                "is_active": True
            },
            {
                "name": "Tic-Tac-Toe",
                "description": "Quick strategy game",
                "image_url": "Tic-Tac-Toe",
                "game_type": "board",
                "min_players": 2,
                "max_players": 2,
                "is_active": True
            },
            {
                "name": "Connect Four",
                "description": "Classic grid game",
                "image_url": "Connect Four",
                "game_type": "board",
                "min_players": 2,
                "max_players": 2,
                "is_active": True
            },
            {
                "name": "Snake",
                "description": "Single-player web snake game",
                "image_url": "Snake",
                "game_type": "arcade",
                "min_players": 1,
                "max_players": 2,
                "is_active": True
            }
        ]

        for gdata in games_to_seed:
            existing = db.query(Game).filter(Game.name == gdata["name"]).first()
            if not existing:
                logger.info(f"Seeding game: {gdata['name']}")
                game = Game(**gdata)
                db.add(game)

        # Seed admin and users
        users_to_seed = [
            {
                "username": "admin",
                "email": "admin@gamebox.com",
                "password_hash": hash_password("admin"),
                "role": "ADMIN",
                "account_status": "ACTIVE"
            },
            {
                "username": "gamer1",
                "email": "gamer1@gamebox.com",
                "password_hash": hash_password("gamer1"),
                "role": "USER",
                "account_status": "ACTIVE"
            },
            {
                "username": "gamer2",
                "email": "gamer2@gamebox.com",
                "password_hash": hash_password("gamer2"),
                "role": "USER",
                "account_status": "ACTIVE"
            }
        ]

        for udata in users_to_seed:
            existing = db.query(User).filter(User.username == udata["username"]).first()
            if not existing:
                logger.info(f"Seeding user: {udata['username']}")
                user = User(**udata)
                db.add(user)

        db.commit()
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

    logger.info("Database initialization completed.")
