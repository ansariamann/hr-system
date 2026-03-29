import email
from email.message import EmailMessage as StdEmailMessage
from unittest.mock import MagicMock
from uuid import uuid4

from ats_backend.email.imap import IMAPPollingService
from ats_backend.email.models import EmailIngestionResponse
from ats_backend.email.parser import EmailParser


def build_raw_email(
    *,
    message_id: str | None = "<test-message@example.com>",
    sender: str = "candidate@example.com",
    subject: str = "Resume Submission",
    attachments: list[tuple[str, str, bytes]] | None = None,
) -> bytes:
    msg = StdEmailMessage()
    msg["From"] = sender
    msg["To"] = "jobs@example.com"
    msg["Subject"] = subject
    if message_id is not None:
        msg["Message-ID"] = message_id
    msg.set_content("Please find the attached resume.")

    for filename, content_type, content in attachments or []:
        maintype, subtype = content_type.split("/", 1)
        msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

    return msg.as_bytes()


class FakeIMAP:
    def __init__(self, messages: dict[bytes, bytes]):
        self.messages = messages
        self.store_calls: list[tuple[bytes, str, str]] = []
        self.login_args = None
        self.selected_mailbox = None
        self.logged_out = False

    def login(self, username: str, password: str):
        self.login_args = (username, password)
        return "OK", []

    def select(self, mailbox: str):
        self.selected_mailbox = mailbox
        return "OK", [b""]

    def search(self, charset, criterion):
        return "OK", [b" ".join(self.messages.keys())]

    def fetch(self, msg_no: bytes, query: str):
        return "OK", [(b"RFC822", self.messages[msg_no])]

    def store(self, msg_no: bytes, operation: str, flags: str):
        self.store_calls.append((msg_no, operation, flags))
        return "OK", []

    def logout(self):
        self.logged_out = True
        return "BYE", []


def apply_imap_settings(monkeypatch, **overrides):
    base = {
        "imap_ingestion_enabled": True,
        "imap_client_id": str(uuid4()),
        "imap_username": "imap-user@gmail.com",
        "imap_password": "app-password",
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "imap_mailbox": "INBOX",
        "imap_max_messages_per_poll": 25,
    }
    base.update(overrides)

    for key, value in base.items():
        monkeypatch.setattr("ats_backend.email.imap.settings." + key, value)


def test_parse_raw_email_bytes_extracts_supported_attachments():
    parser = EmailParser()
    raw_email = build_raw_email(
        attachments=[
            ("resume.pdf", "application/pdf", b"%PDF-1.4 fake"),
            ("notes.txt", "text/plain", b"ignore me"),
        ]
    )

    parsed = parser.parse_raw_email_bytes(raw_email)

    assert parsed.sender == "candidate@example.com"
    assert parsed.subject == "Resume Submission"
    assert len(parsed.attachments) == 1
    assert parsed.attachments[0].filename == "resume.pdf"


def test_parse_raw_email_bytes_generates_message_id_when_missing():
    parser = EmailParser()
    raw_email = build_raw_email(
        message_id=None,
        attachments=[("resume.pdf", "application/pdf", b"%PDF-1.4 fake")],
    )

    parsed = parser.parse_raw_email_bytes(raw_email)

    assert parsed.message_id.startswith("generated-")
    assert parsed.sender == "candidate@example.com"


def test_imap_poller_marks_message_seen_after_success(monkeypatch, mock_db_session):
    apply_imap_settings(monkeypatch)
    raw_email = build_raw_email(
        attachments=[("resume.pdf", "application/pdf", b"%PDF-1.4 fake")]
    )
    fake_imap = FakeIMAP({b"1": raw_email})
    processor = MagicMock()
    processor.process_email.return_value = EmailIngestionResponse(
        success=True,
        message="ok",
        job_ids=[],
        processed_attachments=1,
    )

    service = IMAPPollingService(
        email_processor=processor,
        imap_factory=lambda host, port: fake_imap,
    )

    result = service.poll_inbox(mock_db_session)

    assert result.messages_seen == 1
    assert result.messages_ingested == 1
    assert result.attachments_processed == 1
    assert result.duplicate_messages == 0
    assert fake_imap.store_calls == [(b"1", "+FLAGS", "\\Seen")]


def test_imap_poller_marks_duplicates_seen(monkeypatch, mock_db_session):
    apply_imap_settings(monkeypatch)
    raw_email = build_raw_email(
        attachments=[("resume.pdf", "application/pdf", b"%PDF-1.4 fake")]
    )
    fake_imap = FakeIMAP({b"1": raw_email})
    processor = MagicMock()
    processor.process_email.return_value = EmailIngestionResponse(
        success=True,
        message="duplicate",
        job_ids=[],
        duplicate_message_id="test-message@example.com",
        processed_attachments=0,
    )

    service = IMAPPollingService(
        email_processor=processor,
        imap_factory=lambda host, port: fake_imap,
    )

    result = service.poll_inbox(mock_db_session)

    assert result.duplicate_messages == 1
    assert fake_imap.store_calls == [(b"1", "+FLAGS", "\\Seen")]


def test_imap_poller_marks_unsupported_only_messages_seen(monkeypatch, mock_db_session):
    apply_imap_settings(monkeypatch)
    raw_email = build_raw_email(
        attachments=[("notes.txt", "text/plain", b"plain text")]
    )
    fake_imap = FakeIMAP({b"1": raw_email})
    processor = MagicMock()

    service = IMAPPollingService(
        email_processor=processor,
        imap_factory=lambda host, port: fake_imap,
    )

    result = service.poll_inbox(mock_db_session)

    assert result.messages_seen == 1
    assert result.failures == 1
    assert fake_imap.store_calls == [(b"1", "+FLAGS", "\\Seen")]
    processor.process_email.assert_not_called()


def test_imap_poller_leaves_failed_messages_unread(monkeypatch, mock_db_session):
    apply_imap_settings(monkeypatch)
    raw_email = build_raw_email(
        attachments=[("resume.pdf", "application/pdf", b"%PDF-1.4 fake")]
    )
    fake_imap = FakeIMAP({b"1": raw_email})
    processor = MagicMock()
    processor.process_email.side_effect = RuntimeError("database down")

    service = IMAPPollingService(
        email_processor=processor,
        imap_factory=lambda host, port: fake_imap,
    )

    result = service.poll_inbox(mock_db_session)

    assert result.failures == 1
    assert fake_imap.store_calls == []


def test_imap_poller_respects_max_messages_per_poll(monkeypatch, mock_db_session):
    apply_imap_settings(monkeypatch, imap_max_messages_per_poll=1)
    fake_imap = FakeIMAP(
        {
            b"1": build_raw_email(attachments=[("resume-1.pdf", "application/pdf", b"%PDF-1.4 one")]),
            b"2": build_raw_email(attachments=[("resume-2.pdf", "application/pdf", b"%PDF-1.4 two")]),
        }
    )
    processor = MagicMock()
    processor.process_email.return_value = EmailIngestionResponse(
        success=True,
        message="ok",
        job_ids=[],
        processed_attachments=1,
    )

    service = IMAPPollingService(
        email_processor=processor,
        imap_factory=lambda host, port: fake_imap,
    )

    result = service.poll_inbox(mock_db_session)

    assert result.messages_seen == 1
    assert processor.process_email.call_count == 1


def test_imap_poller_prioritizes_newest_unseen_messages(monkeypatch, mock_db_session):
    apply_imap_settings(monkeypatch, imap_max_messages_per_poll=2)
    fake_imap = FakeIMAP(
        {
            b"1": build_raw_email(
                message_id="<oldest@example.com>",
                attachments=[("resume-1.pdf", "application/pdf", b"%PDF-1.4 one")],
            ),
            b"2": build_raw_email(
                message_id="<middle@example.com>",
                attachments=[("resume-2.pdf", "application/pdf", b"%PDF-1.4 two")],
            ),
            b"3": build_raw_email(
                message_id="<newest@example.com>",
                attachments=[("resume-3.pdf", "application/pdf", b"%PDF-1.4 three")],
            ),
        }
    )
    processor = MagicMock()
    processor.process_email.return_value = EmailIngestionResponse(
        success=True,
        message="ok",
        job_ids=[],
        processed_attachments=1,
    )

    service = IMAPPollingService(
        email_processor=processor,
        imap_factory=lambda host, port: fake_imap,
    )

    result = service.poll_inbox(mock_db_session)

    assert result.messages_seen == 2
    assert processor.process_email.call_count == 2
    processed_ids = [
        call.kwargs["email"].message_id
        for call in processor.process_email.call_args_list
    ]
    assert processed_ids == ["<newest@example.com>", "<middle@example.com>"]
