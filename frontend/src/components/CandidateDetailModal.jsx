import React from "react";
import { Modal, Descriptions, Tag, Typography, Space, Button, Divider, Alert } from "antd";
import {
  User,
  Mail,
  Phone,
  MapPin,
  Calendar,
  Briefcase,
  DollarSign,
  FileText,
  Clock,
  ShieldAlert,
  Building2,
  Send,
} from "lucide-react";

const { Title, Text, Paragraph } = Typography;

export function CandidateDetailModal({
  candidate,
  visible,
  onClose,
  onReviewCandidate,
  onScheduleInterview,
  onSendToClient,
  onOpenAssignModal,
}) {
  if (!candidate) return null;

  const getStatusColor = (status, isBlacklisted) => {
    if (isBlacklisted) return "red";
    switch (status) {
      case "pool":
        return "default";
      case "submitted":
        return "cyan";
      case "interview_scheduled":
        return "purple";
      case "selected":
        return "blue";
      case "joined":
      case "hired":
        return "green";
      case "left_company":
        return "red";
      default:
        return "blue";
    }
  };

  const skillsList = Array.isArray(candidate.skills)
    ? candidate.skills
    : typeof candidate.skills === "string"
    ? candidate.skills.split(",").map((s) => s.trim())
    : [];

  return (
    <Modal
      open={visible}
      onCancel={onClose}
      width={780}
      title={
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: "50%",
              background: "#6366f1",
              color: "#fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 700,
              fontSize: 16,
            }}
          >
            {candidate.name ? candidate.name[0].toUpperCase() : "C"}
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: "#0f172a" }}>
              {candidate.name}
            </div>
            <div style={{ fontSize: 12, color: "#64748b" }}>
              {candidate.company ? `${candidate.company} • ` : ""}
              {candidate.location || "Location not specified"}
            </div>
          </div>
        </div>
      }
      footer={[
        <Button key="close" onClick={onClose}>
          Close
        </Button>,
        <Button
          key="assign"
          icon={<Send size={14} style={{ marginRight: 4 }} />}
          onClick={() => {
            onClose();
            if (onOpenAssignModal) {
              onOpenAssignModal(candidate);
            } else {
              onSendToClient(candidate.id);
            }
          }}
          style={{ color: "#4f46e5", borderColor: "#c7d2fe" }}
        >
          Assign to Client
        </Button>,
        <Button
          key="review"
          icon={<FileText size={14} style={{ marginRight: 4 }} />}
          onClick={() => {
            onClose();
            onReviewCandidate(candidate);
          }}
        >
          Split-Screen Review
        </Button>,
        <Button
          key="interview"
          type="primary"
          icon={<Calendar size={14} style={{ marginRight: 4 }} />}
          onClick={() => {
            onClose();
            onScheduleInterview(candidate);
          }}
          style={{ background: "#6366f1" }}
        >
          Schedule Interview
        </Button>,
      ]}
    >
      <div style={{ padding: "8px 0" }}>
        {candidate.isBlacklisted && (
          <Alert
            message="Quarantined Profile (Ex-Employee)"
            description="This candidate has been flagged as a former employee and is automatically excluded from active talent searches per enterprise compliance."
            type="error"
            showIcon
            icon={<ShieldAlert size={18} />}
            style={{ marginBottom: 16 }}
          />
        )}

        <Descriptions bordered size="small" column={{ xs: 1, sm: 2, md: 3 }}>
          <Descriptions.Item label={<Space><Mail size={13} /> Email</Space>}>
            <Text copyable>{candidate.email}</Text>
          </Descriptions.Item>
          <Descriptions.Item label={<Space><Phone size={13} /> Phone</Space>}>
            {candidate.phone || "—"}
          </Descriptions.Item>
          <Descriptions.Item label="Status">
            <Tag color={getStatusColor(candidate.currentStatus, candidate.isBlacklisted)}>
              {candidate.isBlacklisted
                ? "LEAVER (BLACKLISTED)"
                : (candidate.currentStatus || "pool").toUpperCase()}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label={<Space><Building2 size={13} /> Assigned Client</Space>}>
            {candidate.selectedClientName || candidate.clientName ? (
              <Tag color="blue" icon={<Building2 size={11} style={{ marginRight: 3, verticalAlign: "middle" }} />}>
                {candidate.selectedClientName || candidate.clientName}
              </Tag>
            ) : (
              <Text type="secondary">Unassigned</Text>
            )}
          </Descriptions.Item>
          <Descriptions.Item label={<Space><MapPin size={13} /> Location</Space>}>
            {candidate.location || "Remote"}
          </Descriptions.Item>
          <Descriptions.Item label={<Space><Briefcase size={13} /> Experience</Space>}>
            {candidate.experienceYears ? `${candidate.experienceYears} Years` : "—"}
          </Descriptions.Item>
          <Descriptions.Item label={<Space><Clock size={13} /> Notice Period</Space>}>
            {candidate.noticePeriodDays ? `${candidate.noticePeriodDays} Days` : "Immediate"}
          </Descriptions.Item>
          <Descriptions.Item label={<Space><DollarSign size={13} /> Current CTC</Space>}>
            {candidate.ctcCurrent
              ? `₹${(candidate.ctcCurrent / 100000).toFixed(1)} LPA`
              : "—"}
          </Descriptions.Item>
          <Descriptions.Item label={<Space><DollarSign size={13} /> Expected CTC</Space>}>
            {candidate.ctcExpected
              ? `₹${(candidate.ctcExpected / 100000).toFixed(1)} LPA`
              : "—"}
          </Descriptions.Item>
          <Descriptions.Item label="Candidate ID">
            <Text code>{candidate.id}</Text>
          </Descriptions.Item>
        </Descriptions>

        <Divider orientation="left" style={{ margin: "16px 0 12px 0" }}>
          Technical Skills & Stack
        </Divider>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 16 }}>
          {skillsList.length > 0 ? (
            skillsList.map((skill, index) => (
              <Tag key={index} color="geekblue" style={{ fontSize: 13, padding: "2px 10px", borderRadius: 4 }}>
                {skill}
              </Tag>
            ))
          ) : (
            <Text type="secondary">No skills registered</Text>
          )}
        </div>

        {candidate.notes && (
          <>
            <Divider orientation="left" style={{ margin: "16px 0 12px 0" }}>
              Recruiter & System Notes
            </Divider>
            <Paragraph
              style={{
                background: "#f8fafc",
                padding: 12,
                borderRadius: 8,
                border: "1px solid #e2e8f0",
                fontSize: 13,
                color: "#334155",
              }}
            >
              {candidate.notes}
            </Paragraph>
          </>
        )}

        {candidate.resumeParsed && candidate.resumeParsed.parsedText && (
          <>
            <Divider orientation="left" style={{ margin: "16px 0 12px 0" }}>
              Parsed Resume Excerpt
            </Divider>
            <div
              style={{
                backgroundColor: "#0f172a",
                color: "#f1f5f9",
                padding: 14,
                borderRadius: 8,
                maxHeight: 180,
                overflowY: "auto",
                fontFamily: "monospace",
                fontSize: 12,
                whiteSpace: "pre-wrap",
              }}
            >
              {candidate.resumeParsed.parsedText}
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
