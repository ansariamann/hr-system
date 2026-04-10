from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest

from ats_backend.api.candidates import (
    ScheduleInterviewPayload,
    _get_next_interview_round,
    schedule_interview,
)
from ats_backend.models.candidate import Candidate
from ats_backend.services.candidate_service import CandidateService
from ats_backend.services.application_service import ApplicationService
from ats_backend.schemas.candidate import CandidateCreate, CandidateUpdate
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


def test_create_candidate_keeps_client_blank_until_application():
    service = CandidateService()
    db = MagicMock()

    with patch.object(service.repository, "create") as create_candidate:
        create_candidate.return_value = Candidate(name="Blank Client", client_id=None)
        with patch.object(service.repository.audit_logger, "log_create"):

            service.create_candidate(
                db=db,
                client_id=uuid4(),
                candidate_data=CandidateCreate(name="Blank Client"),
            )

    assert create_candidate.call_args.kwargs["client_id"] is None


def test_create_application_assigns_candidate_to_target_client_when_unassigned():
    service = ApplicationService()
    db = MagicMock()
    target_client_id = uuid4()
    candidate_id = uuid4()
    candidate = SimpleNamespace(
        id=candidate_id,
        client_id=None,
        status="ACTIVE",
        remark=None,
        updated_at=None,
    )

    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = []
    db.query.return_value = query

    with patch("ats_backend.services.application_service.CandidateRepository") as candidate_repo_cls:
        with patch.object(service.repository, "create_with_audit") as create_with_audit:
            create_with_audit.return_value = SimpleNamespace(
                id=uuid4(),
                candidate_id=candidate_id,
                client_id=target_client_id,
                status="RECEIVED",
                job_id=None,
            )
            candidate_repo = candidate_repo_cls.return_value
            candidate_repo.get_by_id_for_client.return_value = None
            candidate_repo.get_by_id.return_value = candidate

            service.create_application(
                db=db,
                client_id=target_client_id,
                application_data=ApplicationCreate(
                    candidate_id=candidate_id,
                    status="RECEIVED",
                ),
            )

    assert candidate.client_id == target_client_id


def test_update_candidate_allows_unassigned_candidate_fallback():
    service = CandidateService()
    db = MagicMock()
    candidate_id = uuid4()
    request_client_id = uuid4()
    unassigned_candidate = SimpleNamespace(id=candidate_id, client_id=None)
    updated_candidate = SimpleNamespace(id=candidate_id, client_id=None, name="Updated Name")

    with patch.object(service.repository, "get_by_id_for_client", return_value=None):
        with patch.object(service.repository, "get_by_id", return_value=unassigned_candidate):
            with patch.object(service.repository, "update_with_audit", return_value=updated_candidate) as update_with_audit:
                result = service.update_candidate(
                    db=db,
                    candidate_id=candidate_id,
                    client_id=request_client_id,
                    candidate_data=CandidateUpdate(name="Updated Name"),
                    user_id=uuid4(),
                )

    assert result is updated_candidate
    assert update_with_audit.call_count == 1
    assert update_with_audit.call_args.kwargs["id"] == candidate_id
    assert update_with_audit.call_args.kwargs["client_id"] == request_client_id


def test_delete_candidate_allows_unassigned_candidate_fallback():
    service = CandidateService()
    db = MagicMock()
    candidate_id = uuid4()
    request_client_id = uuid4()
    unassigned_candidate = SimpleNamespace(id=candidate_id, client_id=None)

    query = MagicMock()
    query.filter.return_value = query
    query.first.return_value = None
    db.query.return_value = query

    with patch.object(service.repository, "get_by_id_for_client", return_value=None):
        with patch.object(service.repository, "get_by_id", return_value=unassigned_candidate):
            with patch.object(service.repository, "delete_with_audit", return_value=True) as delete_with_audit:
                result = service.delete_candidate(
                    db=db,
                    candidate_id=candidate_id,
                    client_id=request_client_id,
                    user_id=uuid4(),
                )

    assert result is True
    assert delete_with_audit.call_count == 1
    assert delete_with_audit.call_args.kwargs["id"] == candidate_id
    assert delete_with_audit.call_args.kwargs["client_id"] == request_client_id


def test_delete_candidate_rejects_when_candidate_is_assigned():
    service = CandidateService()
    db = MagicMock()
    candidate_id = uuid4()
    request_client_id = uuid4()
    candidate = SimpleNamespace(id=candidate_id, client_id=request_client_id)

    query = MagicMock()
    query.filter.return_value = query
    query.first.return_value = SimpleNamespace(id=uuid4())
    db.query.return_value = query

    with patch.object(service.repository, "get_by_id_for_client", return_value=candidate):
        with patch.object(service.repository, "delete_with_audit") as delete_with_audit:
            with pytest.raises(ValueError, match="already assigned"):
                service.delete_candidate(
                    db=db,
                    candidate_id=candidate_id,
                    client_id=request_client_id,
                    user_id=uuid4(),
                )

    delete_with_audit.assert_not_called()


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
