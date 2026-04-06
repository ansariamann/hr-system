from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest

from ats_backend.api.activity_logs import get_activity_logs


@pytest.mark.asyncio
async def test_hr_user_can_access_cross_client_activity_logs():
    target_client_id = uuid4()
    current_client_id = uuid4()
    current_user = SimpleNamespace(id=uuid4(), role="hr_user")
    current_client = SimpleNamespace(id=current_client_id)
    activity_log = SimpleNamespace(
        id=uuid4(),
        client_id=target_client_id,
        user_id=current_user.id,
        action_type="APPLICATION_CREATED",
        entity_id=uuid4(),
        details={},
        created_at=None,
    )

    query = MagicMock()
    query.outerjoin.return_value = query
    query.filter.return_value = query
    query.order_by.return_value = query
    query.offset.return_value = query
    query.limit.return_value = query
    query.all.side_effect = [
        [(activity_log, "HR User", "hr@example.com")],
    ]

    clients_query = MagicMock()
    clients_query.all.return_value = [(target_client_id,)]

    db = MagicMock()
    db.query.side_effect = [clients_query, query]

    with patch("ats_backend.api.activity_logs.with_client_context") as with_client_context_mock:
        with_client_context_mock.return_value.__enter__.return_value = db
        with_client_context_mock.return_value.__exit__.return_value = None
        with patch("ats_backend.api.activity_logs.ActivityLogResponse") as response_model:
            response_model.model_validate.side_effect = lambda log: SimpleNamespace(
                id=log.id,
                client_id=log.client_id,
                user_id=log.user_id,
                action_type=log.action_type,
                entity_id=log.entity_id,
                details=log.details,
                created_at=log.created_at,
                user_name=None,
            )

            results = await get_activity_logs(
                db=db,
                current_user=current_user,
                current_client=current_client,
            )

    assert len(results) == 1
    assert results[0].action_type == "APPLICATION_CREATED"
    assert results[0].user_name == "HR User"
