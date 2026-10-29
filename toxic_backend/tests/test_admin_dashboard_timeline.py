from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from toxic_backend.app.database import Base
from toxic_backend.app.models import ChatMessage
from toxic_backend.app.routes.admin import (
    _build_daily_timeline,
    _display_category_distribution,
    list_flagged_messages,
    _resolve_calendar_window,
)


def test_calendar_window_uses_client_local_date_boundaries():
    (
        _timezone,
        start,
        end,
        start_utc,
        end_utc,
    ) = _resolve_calendar_window("2026-10-29", "2026-10-29", "Asia/Kolkata")

    assert start == date(2026, 10, 29)
    assert end == date(2026, 10, 29)
    assert start_utc.isoformat() == "2026-10-28T18:30:00+00:00"
    assert end_utc.isoformat() == "2026-10-29T18:30:00+00:00"


def test_calendar_window_rejects_invalid_date_or_timezone():
    with pytest.raises(HTTPException, match="Invalid timezone"):
        _resolve_calendar_window(None, None, "Not/A-Timezone")

    with pytest.raises(HTTPException, match="YYYY-MM-DD"):
        _resolve_calendar_window("29-10-2026", None, "Asia/Kolkata")


def test_empty_days_are_not_misreported_as_zero_percent():
    timeline = _build_daily_timeline(
        date(2026, 10, 28),
        date(2026, 10, 30),
        {
            date(2026, 10, 28): (23, 11),
            date(2026, 10, 30): (4, 0),
        },
    )

    assert timeline == [
        {
            "date": "2026-10-28",
            "total": 23,
            "toxic": 11,
            "toxicity_rate": 47.8,
            "safe": 12,
        },
        {
            "date": "2026-10-29",
            "total": 0,
            "toxic": 0,
            "toxicity_rate": None,
            "safe": 0,
        },
        {
            "date": "2026-10-30",
            "total": 4,
            "toxic": 0,
            "toxicity_rate": 0.0,
            "safe": 4,
        },
    ]


def test_category_chart_only_counts_current_gametox_labels():
    distribution = _display_category_distribution({
        "Insults & Flaming": 26,
        "Other Offensive Texts": 4,
        "Hate & Harassment": 3,
        "gender": 10,
        "General Toxicity": 18,
        "religion": 2,
        "Gender-Based Toxicity": 1,
        "other_cyberbullying": 1,
    }, non_toxic_count=39)

    assert distribution == {
        "Non-Toxic": 39,
        "Insults & Flaming": 26,
        "Other Offensive Texts": 4,
        "Hate & Harassment": 3,
        "Threats": 0,
        "Extremism": 0,
    }
    assert sum(distribution.values()) == 72


def test_category_chart_normalizes_spacing_and_ignores_unmapped_labels():
    distribution = _display_category_distribution({
        "  insults   & FLAMING ": 2,
        "Toxic": 3,
    }, non_toxic_count=5)

    assert distribution == {
        "Non-Toxic": 5,
        "Insults & Flaming": 2,
        "Other Offensive Texts": 0,
        "Hate & Harassment": 0,
        "Threats": 0,
        "Extremism": 0,
    }


def test_flagged_messages_all_categories_include_binary_and_non_toxic_predictions():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([
        ChatMessage(
            message="safe message",
            prediction="Non-Toxic",
            status="Safe",
            confidence=90.0,
            selected_model="test",
        ),
        ChatMessage(
            message="spacing variant",
            prediction=" nOn - tOxIc ",
            status="Non-Toxic",
            confidence=90.0,
            selected_model="test",
        ),
        ChatMessage(
            message="toxic message",
            prediction="Threats",
            status="Toxic",
            confidence=90.0,
            selected_model="test",
        ),
        ChatMessage(
            message="binary toxic message",
            prediction="Toxic",
            status="Toxic",
            confidence=90.0,
            selected_model="test",
        ),
    ])
    session.commit()

    non_toxic_messages = list_flagged_messages(
        prediction="Non-Toxic",
        db=session,
        admin=None,
    )
    binary_toxic_messages = list_flagged_messages(
        prediction="Toxic",
        db=session,
        admin=None,
    )
    all_category_messages = list_flagged_messages(db=session, admin=None)

    assert {message["message"] for message in non_toxic_messages} == {
        "safe message",
        "spacing variant",
    }
    assert {message["message"] for message in binary_toxic_messages} == {
        "binary toxic message",
    }
    assert {message["message"] for message in all_category_messages} == {
        "safe message",
        "spacing variant",
        "toxic message",
        "binary toxic message",
    }

    session.close()
    engine.dispose()
