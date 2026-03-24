from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest

from ats_backend.api.candidates import ScheduleInterviewPayload, schedule_interview
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
        candidate_repo_cls.return_value.get_by_id_for_client.return_value = None

        with pytest.raises(ValueError, match="Candidate not found for the selected client"):
            service.create_application(
                db=db,
                client_id=uuid4(),
                application_data=ApplicationCreate(
                    candidate_id=uuid4(),
                    status="RECEIVED",
                ),
            )
