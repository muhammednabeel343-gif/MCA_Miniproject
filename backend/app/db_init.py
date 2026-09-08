import logging
from sqlalchemy import text
from .database import engine, Base
from .models import Game, User
from .services.auth import hash_password

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db_init")


def init_db():
    logger.info("Initializing database...")

    # 1. Update/alter chat_messages table if it already exists
    with engine.connect() as conn:
        logger.info("Checking chat_messages table for columns...")
        # We can add columns safely with ALTER TABLE ADD COLUMN IF NOT EXISTS
        alter_queries = [
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;",
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS game_id INTEGER REFERENCES games(id) ON DELETE SET NULL;",
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS room_id INTEGER REFERENCES game_rooms(id) ON DELETE SET NULL;",
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS logistic_regression_prediction VARCHAR;",
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS logistic_regression_confidence FLOAT;",
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS svm_prediction VARCHAR;",
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS svm_confidence FLOAT;"
        ]
        for query in alter_queries:
            try:
                conn.execute(text(query))
                conn.commit()
            except Exception as e:
                logger.error(f"Error executing alter query: {query}. Error: {e}")

    # 2. Create other tables
    logger.info("Creating remaining tables...")
    Base.metadata.create_all(bind=engine)

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
