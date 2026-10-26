import React, { useState } from "react";
import { Modal, Form, Select, Input, Button, Typography, Space, Tag, Avatar, Alert } from "antd";
import { Building2, UserCheck, Send, Briefcase, Mail } from "lucide-react";

const { Text, Title } = Typography;
const { TextArea } = Input;

export function AssignCandidateModal({
  visible,
  candidate,
  clients = [],
  onClose,
  onAssign,
}) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  React.useEffect(() => {
    if (visible && candidate) {
      form.setFieldsValue({
        clientId: candidate.clientId || (clients.length > 0 ? clients[0].id : undefined),
        targetRole: candidate.keySkill || (candidate.skills && candidate.skills[0]) || "Senior Software Engineer",
        notes: `Profile presented for evaluation. Experience: ${candidate.experienceYears || 0} yrs.`,
      });
    }
  }, [visible, candidate, clients, form]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      const selectedClient = clients.find((c) => c.id === values.clientId);
      const clientName = selectedClient ? selectedClient.name : "Client Organization";

      await onAssign(candidate.id, values.clientId, clientName, values.notes, values.targetRole);
      setLoading(false);
      onClose();
    } catch (err) {
      setLoading(false);
    }
  };

  if (!candidate) return null;

  return (
    <Modal
      open={visible}
      onCancel={onClose}
      footer={null}
      destroyOnClose
      width={560}
      title={
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 8,
              background: "#eff6ff",
              color: "#2563eb",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Building2 size={20} />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 16, color: "#0f172a" }}>
              Assign Candidate to Client
            </div>
            <div style={{ fontSize: 12, color: "#64748b" }}>
              Submit profile to client portal and grant client review access
            </div>
          </div>
        </div>
      }
    >
      {/* Candidate Summary Card */}
      <div
        style={{
          backgroundColor: "#f8fafc",
          borderRadius: 8,
          border: "1px solid #e2e8f0",
          padding: "14px 16px",
          marginTop: 12,
          marginBottom: 18,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Avatar
            size={42}
            style={{
              backgroundColor: "#4f46e5",
              fontWeight: 700,
              fontSize: 16,
            }}
          >
            {candidate.name?.charAt(0) || "C"}
          </Avatar>
          <div>
            <div style={{ fontWeight: 700, color: "#0f172a", fontSize: 15 }}>
              {candidate.name}
            </div>
            <div style={{ fontSize: 12, color: "#64748b", display: "flex", alignItems: "center", gap: 6 }}>
              <span>{candidate.location || "Remote"}</span>
              <span>•</span>
              <span>{candidate.experienceYears || 0} yrs exp</span>
              {candidate.clientName && (
                <>
                  <span>•</span>
                  <Tag color="blue" style={{ margin: 0, fontSize: 11 }}>
                    Currently: {candidate.clientName}
                  </Tag>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Form.Item
          name="clientId"
          label={
            <span style={{ fontWeight: 600, color: "#1e293b" }}>
              Select Target Client Organization *
            </span>
          }
          rules={[{ required: true, message: "Please select a client" }]}
        >
          <Select
            size="large"
            placeholder="Select a client company..."
            showSearch
            filterOption={(input, option) =>
              (option?.label ?? "").toLowerCase().includes(input.toLowerCase())
            }
            options={clients.map((c) => ({
              value: c.id,
              label: `${c.name} (${c.industry || "General"}) — ${c.emailDomain || "Portal"}`,
            }))}
          />
        </Form.Item>

        <Form.Item
          name="targetRole"
          label={
            <span style={{ fontWeight: 600, color: "#1e293b" }}>
              Target Position / Job Requisition
            </span>
          }
        >
          <Input
            size="large"
            prefix={<Briefcase size={16} style={{ color: "#94a3b8" }} />}
            placeholder="e.g. Senior Full-Stack Engineer, DevOps Lead"
          />
        </Form.Item>

        <Form.Item
          name="notes"
          label={
            <span style={{ fontWeight: 600, color: "#1e293b" }}>
              Submission Pitch & Evaluation Notes
            </span>
          }
        >
          <TextArea
            rows={3}
            placeholder="Include relevant strengths, salary expectations, interview availability, or reason for recommendation..."
          />
        </Form.Item>

        <Alert
          type="info"
          showIcon
          message="Client Portal Sync"
          description="Assigning will transition candidate status to 'Submitted'. The client admin will immediately see this candidate on their Client Portal Kanban review board."
          style={{ marginBottom: 20, fontSize: 12 }}
        />

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <Button onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            type="primary"
            htmlType="submit"
            loading={loading}
            icon={<Send size={15} />}
            style={{
              background: "linear-gradient(135deg, #4f46e5 0%, #6366f1 100%)",
              borderColor: "#4f46e5",
            }}
          >
            Confirm Assignment & Send
          </Button>
        </div>
      </Form>
    </Modal>
  );
}
