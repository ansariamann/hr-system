from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import MagicMock, patch

from ats_backend.api.clients import invite_user
from ats_backend.auth.models import PasswordResetToken, User


def test_invite_user_generates_real_password_setup_token(mock_db_session):
    client_id = uuid4()
    acting_user_id = uuid4()
    admin_user_id = uuid4()

    client = SimpleNamespace(id=client_id, name="Acme Corp")
    current_user = SimpleNamespace(id=acting_user_id, client_id=client_id, role="hr_admin")
    admin_user = SimpleNamespace(
        id=admin_user_id,
        client_id=client_id,
        role="client_admin",
        is_active=True,
        email="client.admin@acme.com",
        full_name="Acme Admin",
        created_at=datetime.utcnow(),
    )

    user_query = MagicMock()
    user_query.filter.return_value.order_by.return_value.first.return_value = admin_user
    mock_db_session.query.return_value = user_query

    with patch("ats_backend.api.clients.ClientService.get_client_by_id", return_value=client), \
         patch("ats_backend.api.clients.save_email_as_text", return_value="storage/generated_emails/invite.txt"), \
         patch("ats_backend.api.clients.send_email", return_value=True), \
         patch("ats_backend.api.clients.settings.environment", "development"), \
         patch("ats_backend.api.clients.settings.frontend_client_url", "http://localhost:5174"), \
         patch("ats_backend.api.clients.settings.password_reset_token_minutes", 30):
        response = invite_user(client_id=client_id, db=mock_db_session, current_user=current_user)

    added_objects = [call.args[0] for call in mock_db_session.add.call_args_list]
    reset_tokens = [obj for obj in added_objects if isinstance(obj, PasswordResetToken)]

    assert response.client_id == client_id
    assert response.invited_user_email == admin_user.email
    assert response.invite_emailed is True
    assert response.generated_email_path == "storage/generated_emails/invite.txt"
    assert response.invite_link.startswith("http://localhost:5174/reset-password?token=")
    assert response.token is not None
    assert len(reset_tokens) == 1
    assert reset_tokens[0].user_id == admin_user_id
    assert reset_tokens[0].token_hash
    mock_db_session.commit.assert_called_once()
    mock_db_session.query.assert_called_with(User)
