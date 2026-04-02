from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest

from ats_backend.api.candidates import (
    ScheduleInterviewPayload,
    _get_next_interview_round,
    schedule_interview,
)
from ats_backend.services.application_service import ApplicationService
from ats_backend.schemas.application import ApplicationCreate


@pytest.mark.asyncio
async def test_schedule_interview_uses_application_fallback_for_legacy_client_mismatch():
    candidate_id = uuid4()
    client_id = uuid4()
    candidate = SimpleNamespace(
        id=candidate_id,
        client_id=uuid4(),
        status="ACTIVE",
        updated_at=None,
    )
    application = SimpleNamespace(
        id=uuid4(),
        client_id=client_id,
        candidate=candidate,
    )
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.first.return_value = application

    db = MagicMock()
    db.query.return_value = query

    current_user = SimpleNamespace(id=uuid4(), role="client_admin")
    current_client = SimpleNamespace(id=client_id)

    with patch("ats_backend.api.candidates.CandidateService") as candidate_service_cls:
        candidate_service_cls.return_value.get_candidate_by_id_for_client.return_value = None

        updated = await schedule_interview(
            candidate_id=candidate_id,
            payload=ScheduleInterviewPayload(
                scheduledDate="2026-03-24T10:30:00Z",
                roundNumber=1,
                notes="Intro call",
            ),
            db=db,
            current_user=current_user,
            current_client=current_client,
        )

    assert updated is candidate
    assert candidate.status == "INTERVIEW_SCHEDULED"
    db.commit.assert_called_once()


def test_create_application_rejects_candidate_outside_selected_client():
    service = ApplicationService()
    db = MagicMock()

    with patch("ats_backend.services.application_service.CandidateRepository") as candidate_repo_cls:
        candidate_mock = MagicMock()
        candidate_mock.client_id = uuid4()
        candidate_repo_cls.return_value.get_by_id.return_value = candidate_mock

        with pytest.raises(ValueError, match="Candidate not found for the selected client"):
            service.create_application(
                db=db,
                client_id=uuid4(),
                application_data=ApplicationCreate(
                    candidate_id=uuid4(),
                    status="RECEIVED",
                ),
            )


def test_get_next_interview_round_defaults_to_one_when_no_prior_rounds():
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = []

    db = MagicMock()
    db.query.return_value = query

    next_round = _get_next_interview_round(db, uuid4(), uuid4())

    assert next_round == 1


def test_get_next_interview_round_advances_from_latest_logged_round():
    logs = [
        SimpleNamespace(reason="Interview scheduled | Round: 1"),
        SimpleNamespace(reason="Interview scheduled | Round: 2 | Notes: Follow-up"),
        SimpleNamespace(reason="Interview scheduled | Round: 4"),
    ]
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = logs

    db = MagicMock()
    db.query.return_value = query

    next_round = _get_next_interview_round(db, uuid4(), uuid4())

    assert next_round == 5


@pytest.mark.asyncio
async def test_schedule_interview_rejects_skipped_round():
    candidate_id = uuid4()
    client_id = uuid4()
    candidate = SimpleNamespace(
        id=candidate_id,
        client_id=client_id,
        status="ACTIVE",
        updated_at=None,
    )
    current_user = SimpleNamespace(id=uuid4(), role="client_admin")
    current_client = SimpleNamespace(id=client_id)

    with patch("ats_backend.api.candidates._resolve_candidate_for_client_access", return_value=candidate), \
         patch("ats_backend.api.candidates._get_next_interview_round", return_value=2):
        with pytest.raises(Exception) as exc_info:
            await schedule_interview(
                candidate_id=candidate_id,
                payload=ScheduleInterviewPayload(
                    scheduledDate="2026-03-24T10:30:00Z",
                    roundNumber=3,
                    notes="Skipped round",
                ),
                db=MagicMock(),
                current_user=current_user,
                current_client=current_client,
            )

    assert "round 2" in str(exc_info.value)
