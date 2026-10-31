import React, { useState, useEffect } from "react";
import { Modal, Button, Card, Typography, Space, Tag, Alert, message, Spin } from "antd";
import { Mail, RefreshCw, CheckCircle2, Clock, Inbox, ShieldCheck } from "lucide-react";
import { api } from "../api";

const { Text, Title, Paragraph } = Typography;

export function EmailIngestionModal({ open, onClose, onRefreshCandidates }) {
  const [loading, setLoading] = useState(false);
  const [polling, setPolling] = useState(false);
  const [status, setStatus] = useState(null);
  const [lastPollResult, setLastPollResult] = useState(null);

  const loadStatus = async () => {
    setLoading(true);
    try {
      const data = await api.getEmailStatus();
      setStatus(data);
    } catch (err) {
      console.error("Failed to load email poller status:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      loadStatus();
    }
  }, [open]);

  const handleManualPoll = async () => {
    setPolling(true);
    try {
      const res = await api.pollEmailInbox();
      setLastPollResult(res);
      if (res.messagesIngested > 0) {
        message.success(`Imported ${res.messagesIngested} candidate resume(s) from inbox!`);
        if (onRefreshCandidates) onRefreshCandidates();
      } else {
        message.info(res.message || "Inbox checked. No new unread resume emails found.");
      }
      loadStatus();
    } catch (err) {
      message.error("Failed to poll email inbox: " + (err.message || "Unknown error"));
    } finally {
      setPolling(false);
    }
  };

  return (
    <Modal
      title={
        <Space>
          <Mail size={18} style={{ color: "#4f46e5" }} />
          <span style={{ fontWeight: 700 }}>Email Resume Ingestion Pipeline (IMAP)</span>
        </Space>
      }
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="close" onClick={onClose}>
          Close
        </Button>,
        <Button
          key="poll"
          type="primary"
          icon={<RefreshCw size={14} className={polling ? "animate-spin" : ""} style={{ marginRight: 4 }} />}
          style={{ background: "#4f46e5", borderColor: "#4f46e5" }}
          loading={polling}
          onClick={handleManualPoll}
        >
          Check Inbox Now
        </Button>,
      ]}
      width={640}
      destroyOnClose
    >
      <div style={{ padding: "8px 0" }}>
        <Paragraph type="secondary" style={{ fontSize: 13 }}>
          Automated email pipeline connects directly to your recruitment inbox via IMAP SSL.
          Candidate resumes attached to incoming emails are automatically parsed by Apache PDFBox and OCR,
          creating candidate records in real time.
        </Paragraph>

        {loading ? (
          <div style={{ textAlign: "center", padding: "30px 0" }}>
            <Spin size="large" />
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {/* Status Card */}
            <Card
              size="small"
              style={{ background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0" }}
            >
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <Text type="secondary" style={{ fontSize: 11 }}>PIPELINE STATUS</Text>
                  <div style={{ marginTop: 2 }}>
                    <Tag color="green" icon={<CheckCircle2 size={12} style={{ marginRight: 3, verticalAlign: "middle" }} />}>
                      READY / LISTENING
                    </Tag>
                  </div>
                </div>

                <div>
                  <Text type="secondary" style={{ fontSize: 11 }}>IMAP SERVER</Text>
                  <div style={{ fontWeight: 600, fontSize: 13, marginTop: 2 }}>
                    {status?.imapHost || "imap.gmail.com"}:{status?.imapPort || 993}
                  </div>
                </div>

                <div>
                  <Text type="secondary" style={{ fontSize: 11 }}>INBOX FOLDER</Text>
                  <div style={{ fontWeight: 600, fontSize: 13, marginTop: 2 }}>
                    {status?.imapFolder || "INBOX"}
                  </div>
                </div>

                <div>
                  <Text type="secondary" style={{ fontSize: 11 }}>LAST POLLED</Text>
                  <div style={{ fontWeight: 600, fontSize: 13, marginTop: 2, color: "#64748b" }}>
                    {status?.lastPollTime || "Just now"}
                  </div>
                </div>
              </div>
            </Card>

            {/* Poll Result Feedback */}
            {lastPollResult && (
              <Alert
                message="Last Inbox Scan Result"
                description={lastPollResult.message || `Seen: ${lastPollResult.messagesSeen || 0}, Ingested: ${lastPollResult.messagesIngested || 0}`}
                type={lastPollResult.success ? "success" : "warning"}
                showIcon
              />
            )}

            {/* How to use */}
            <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", padding: 12, borderRadius: 8 }}>
              <Space orientation="vertical" size={2}>
                <Text strong style={{ color: "#166534", fontSize: 13 }}>
                  📩 How to Ingest Resumes via Email:
                </Text>
                <Text style={{ fontSize: 12, color: "#15803d" }}>
                  1. Have applicants send their resumes to your recruitment mailbox or forward applicant emails to it.
                </Text>
                <Text style={{ fontSize: 12, color: "#15803d" }}>
                  2. Supported attachment formats: <strong>PDF, DOCX, DOC, TXT</strong>.
                </Text>
                <Text style={{ fontSize: 12, color: "#15803d" }}>
                  3. The Java backend background worker runs every 5 minutes, or click <strong>"Check Inbox Now"</strong> above to poll immediately.
                </Text>
              </Space>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}

