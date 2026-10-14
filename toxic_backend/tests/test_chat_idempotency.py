import asyncio
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from toxic_backend.app.database import Base
from toxic_backend.app.models import (
    ChatMessage,
    Game,
    GameRoom,
    GameRoomPlayer,
    ModerationAction,
    User,
)
from toxic_backend.app.routes import chat_ws


class ChatIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.user = User(
            username="player",
            email="player@example.test",
            password_hash="not-used",
        )
        game = Game(name="Test Game")
        self.session.add_all([self.user, game])
        self.session.commit()
        self.room = GameRoom(game_id=game.id, room_name="Test Room")
        self.session.add(self.room)
        self.session.commit()
        self.second_user = User(
            username="second-player",
            email="second-player@example.test",
            password_hash="not-used",
        )
        self.session.add(self.second_user)
        self.session.flush()
        self.session.add_all([
            GameRoomPlayer(room_id=self.room.id, user_id=self.user.id),
            GameRoomPlayer(room_id=self.room.id, user_id=self.second_user.id),
        ])
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_retried_client_message_is_saved_and_moderated_once(self):
        prediction = {
            "prediction": "Threats",
            "status": "Toxic",
            "confidence": 61.0,
            "selected_model": "test model",
            "logistic_regression_prediction": "Threats",
            "logistic_regression_confidence": 60.0,
            "svm_prediction": "Threats",
            "svm_confidence": 62.0,
        }
        with patch.object(chat_ws, "predict_message", return_value=prediction) as predict:
            original, created = chat_ws.persist_chat_message(
                self.session, self.user, self.room, "I will kill you", "client-123"
            )
            retried, retry_created = chat_ws.persist_chat_message(
                self.session, self.user, self.room, "I will kill you", "client-123"
            )

        self.assertTrue(created)
        self.assertFalse(retry_created)
        self.assertEqual(original.id, retried.id)
        self.assertEqual(retried.client_message_id, "client-123")
        predict.assert_called_once_with("I will kill you")
        self.assertEqual(self.session.query(ChatMessage).count(), 1)
        self.assertEqual(self.session.query(ModerationAction).count(), 1)
        self.assertEqual(self.user.warning_count, 1)

    def test_prediction_failure_does_not_persist_a_message(self):
        with patch.object(
            chat_ws,
            "predict_message",
            side_effect=RuntimeError("prediction unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "prediction unavailable"):
                chat_ws.persist_chat_message(
                    self.session, self.user, self.room, "test message", "client-456"
                )

        self.assertEqual(self.session.query(ChatMessage).count(), 0)
        self.assertEqual(self.session.query(ModerationAction).count(), 0)

    def test_rest_retry_is_persisted_once_and_visible_to_other_room_player(self):
        prediction = {
            "prediction": "Threats",
            "status": "Toxic",
            "confidence": 61.0,
            "selected_model": "test model",
            "logistic_regression_prediction": "Threats",
            "logistic_regression_confidence": 60.0,
            "svm_prediction": "Threats",
            "svm_confidence": 62.0,
        }
        payload = chat_ws.RoomChatMessage(
            message="I will kill you",
            client_message_id="rest-client-123",
        )

        with patch.object(
            chat_ws,
            "predict_message",
            return_value=prediction,
        ) as predict:
            first_response = chat_ws.send_room_chat_message(
                self.room.id, payload, self.session, self.user
            )
            retry_response = chat_ws.send_room_chat_message(
                self.room.id, payload, self.session, self.user
            )
            polled_messages = chat_ws.get_room_chat_messages(
                self.room.id, 0, self.session, self.second_user
            )

        predict.assert_called_once_with("I will kill you")
        self.assertEqual(first_response["id"], retry_response["id"])
        self.assertEqual(first_response["client_message_id"], "rest-client-123")
        self.assertEqual(first_response["prediction"], "Threats")
        self.assertEqual(first_response["status"], "Toxic")
        self.assertTrue(first_response["warning_triggered"])
        self.assertEqual(len(polled_messages), 1)
        self.assertEqual(polled_messages[0]["id"], first_response["id"])
        self.assertEqual(polled_messages[0]["prediction"], "Threats")
        self.assertTrue(polled_messages[0]["warning_triggered"])
        self.assertEqual(self.session.query(ChatMessage).count(), 1)
        self.assertEqual(self.session.query(ModerationAction).count(), 1)
        self.assertEqual(self.user.warning_count, 1)

    def test_polling_after_id_does_not_return_older_messages(self):
        prediction = {
            "prediction": "Non-Toxic",
            "status": "Safe",
            "confidence": 80.0,
            "selected_model": "test model",
            "logistic_regression_prediction": "Non-Toxic",
            "logistic_regression_confidence": 80.0,
            "svm_prediction": "Non-Toxic",
            "svm_confidence": 80.0,
        }
        with patch.object(chat_ws, "predict_message", return_value=prediction):
            first, _ = chat_ws.persist_chat_message(
                self.session, self.user, self.room, "first", "poll-1"
            )
            second, _ = chat_ws.persist_chat_message(
                self.session, self.second_user, self.room, "second", "poll-2"
            )

        response = chat_ws.get_room_chat_messages(
            self.room.id, first.id, self.session, self.user
        )

        self.assertEqual([message["id"] for message in response], [second.id])
        self.assertFalse(response[0]["warning_triggered"])

    def test_rest_send_rejects_non_member(self):
        outsider = User(
            username="outsider",
            email="outsider@example.test",
            password_hash="not-used",
        )
        self.session.add(outsider)
        self.session.commit()

        with self.assertRaises(HTTPException) as error:
            chat_ws.send_room_chat_message(
                self.room.id,
                chat_ws.RoomChatMessage(message="hello", client_message_id="outsider"),
                self.session,
                outsider,
            )
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(self.session.query(ChatMessage).count(), 0)

    def test_rest_send_rejects_blocked_user_before_prediction(self):
        self.user.account_status = "BLOCKED"
        self.session.add(ModerationAction(
            user_id=self.user.id,
            action_type="BLOCK",
            reason="test",
        ))
        self.session.commit()

        with patch.object(chat_ws, "predict_message") as predict:
            with self.assertRaises(HTTPException) as error:
                chat_ws.send_room_chat_message(
                    self.room.id,
                    chat_ws.RoomChatMessage(
                        message="blocked message",
                        client_message_id="blocked-client",
                    ),
                    self.session,
                    self.user,
                )

        self.assertEqual(error.exception.status_code, 403)
        predict.assert_not_called()
        self.assertEqual(self.session.query(ChatMessage).count(), 0)

    def test_websocket_rejects_non_member(self):
        class FakeWebSocket:
            accepted = False
            close_code = None
            close_reason = None

            async def accept(self):
                self.accepted = True

            async def close(self, code, reason):
                self.close_code = code
                self.close_reason = reason

        outsider = User(
            username="websocket-outsider",
            email="websocket-outsider@example.test",
            password_hash="not-used",
        )
        self.session.add(outsider)
        self.session.commit()
        websocket = FakeWebSocket()

        with (
            patch.object(chat_ws, "SessionLocal", return_value=self.session),
            patch.object(
                chat_ws,
                "decode_access_token",
                return_value={"sub": outsider.username},
            ),
        ):
            asyncio.run(
                chat_ws.websocket_chat_endpoint(
                    self.room.id,
                    websocket,
                    token="test-token",
                )
            )

        self.assertTrue(websocket.accepted)
        self.assertEqual(websocket.close_code, 1008)
        self.assertIn("not a player", websocket.close_reason)
        self.assertNotIn(self.room.id, chat_ws.manager.active_connections)

    def test_serialized_prediction_preserves_all_six_categories(self):
        category_names = {
            0: "Non-Toxic",
            1: "Insults & Flaming",
            2: "Other Offensive Texts",
            3: "Hate & Harassment",
            4: "Threats",
            5: "Extremism",
        }

        for label, name in category_names.items():
            with self.subTest(label=label):
                record = SimpleNamespace(
                    id=label + 1,
                    client_message_id=f"class-{label}",
                    user_id=self.user.id,
                    user=self.user,
                    message=f"sample {label}",
                    status="Safe" if label == 0 else "Toxic",
                    prediction=name,
                    confidence=50.0,
                    created_at=datetime.now(timezone.utc),
                )

                result = chat_ws.serialize_chat_message(record)

                self.assertEqual(result["prediction"], name)
                self.assertEqual(result["status"], record.status)
                self.assertEqual(result["warning_triggered"], label != 0)
                self.assertFalse(result["confidence_is_calibrated"])


if __name__ == "__main__":
    unittest.main()
