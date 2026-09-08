from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .models import ChatMessage
from .db_init import init_db
from .routes.predict import router as predict_router
from .routes.history import router as history_router
from .routes.auth import router as auth_router
from .routes.games import router as games_router
from .routes.chat_ws import router as chat_ws_router
from .routes.users import router as users_router
from .routes.admin import router as admin_router


app = FastAPI(
    title="Toxic Chat Detection API"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "https://toxic-frontend-7xfnew6ak-muhammednabeel343-gifs-projects.vercel.app",
    
],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def read_root():
    return {
        "message": "Toxic Chat Detection API is running"
    }


app.include_router(predict_router)
app.include_router(history_router)
app.include_router(auth_router)
app.include_router(games_router)
app.include_router(chat_ws_router)
app.include_router(users_router)
app.include_router(admin_router)
