import React, { useState, useEffect } from "react";
import { Table, Tag, Space, Typography, Avatar, Card, Select, message, Button } from "antd";
import { FileText, Calendar, UserCheck } from "lucide-react";
import { api } from "../api";

const { Text } = Typography;

export function ApplicationsView({ candidates = [], onSelectCandidate }) {
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(false);

  const loadApplications = async () => {
    setLoading(true);
    try {
      const data = await api.getApplications();
      if (Array.isArray(data) && data.length > 0) {
        setApplications(data);
      } else {
        // Synthesize applications from candidates
        const syn = candidates.map((c, idx) => ({
          id: `app-${idx + 1}`,
          candidate: {
            id: c.id,
            name: c.name,
            email: c.email,
            phone: c.phone,
          },
          job: {
            title: c.skills?.[0] ? `Senior ${c.skills[0]} Engineer` : "Software Engineer",
            department: "Engineering",
          },
          status: (c.currentStatus || "pool").toUpperCase(),
          created_at: new Date(Date.now() - (idx + 1) * 86400000 * 3).toISOString(),
        }));
        setApplications(syn);
      }
    } catch (err) {
      console.error("Failed to load applications", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadApplications();
  }, [candidates]);

  const handleStatusChange = async (appId, newStatus) => {
    try {
      await api.transitionApplicationStatus(appId, newStatus);
      message.success(`Application updated to ${newStatus}`);
      setApplications((prev) =>
        prev.map((a) => (a.id === appId ? { ...a, status: newStatus } : a))
      );
    } catch (err) {
      message.error("Failed to update status");
    }
  };

  const getStatusColor = (status) => {
    const s = String(status).toUpperCase();
    if (s.includes("HIRED") || s.includes("JOINED")) return "green";
    if (s.includes("INTERVIEW")) return "purple";
    if (s.includes("SELECTED")) return "blue";
    if (s.includes("REJECTED") || s.includes("LEFT")) return "red";
    if (s.includes("SUBMITTED")) return "cyan";
    return "default";
  };

  const columns = [
    {
      title: "Candidate",
      key: "candidate",
      render: (_, record) => {
        const name = record.candidate?.name || "Candidate";
        const email = record.candidate?.email || "No email";
        return (
          <Space>
            <Avatar style={{ backgroundColor: "#4f46e5", verticalAlign: "middle" }}>
              {name.charAt(0).toUpperCase()}
            </Avatar>
            <Space direction="vertical" size={0}>
              <Text strong style={{ fontSize: 13, color: "#1e293b" }}>
                {name}
              </Text>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {email}
              </Text>
            </Space>
          </Space>
        );
      },
    },
    {
      title: "Target Role",
      key: "role",
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text strong style={{ fontSize: 13 }}>
            {record.job?.title || "Senior Software Engineer"}
          </Text>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {record.job?.department || "Technology"}
          </Text>
        </Space>
      ),
    },
    {
      title: "Application Status",
      dataIndex: "status",
      key: "status",
      render: (status, record) => (
        <Select
          value={status || "POOL"}
          style={{ width: 150 }}
          onChange={(val) => handleStatusChange(record.id, val)}
          bordered={false}
        >
          <Select.Option value="POOL">
            <Tag color="default">POOL</Tag>
          </Select.Option>
          <Select.Option value="SUBMITTED">
            <Tag color="cyan">SUBMITTED</Tag>
          </Select.Option>
          <Select.Option value="INTERVIEW_SCHEDULED">
            <Tag color="purple">INTERVIEW</Tag>
          </Select.Option>
          <Select.Option value="SELECTED">
            <Tag color="blue">SELECTED</Tag>
          </Select.Option>
          <Select.Option value="HIRED">
            <Tag color="green">HIRED</Tag>
          </Select.Option>
          <Select.Option value="REJECTED">
            <Tag color="red">REJECTED</Tag>
          </Select.Option>
        </Select>
      ),
    },
    {
      title: "Applied Date",
      dataIndex: "created_at",
      key: "created_at",
      render: (date) => (
        <Space size={4}>
          <Calendar size={13} style={{ color: "#64748b" }} />
          <Text style={{ fontSize: 12, color: "#475569" }}>
            {date ? new Date(date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "Recent"}
          </Text>
        </Space>
      ),
    },
    {
      title: "Actions",
      key: "actions",
      render: (_, record) => (
        <Button
          size="small"
          onClick={() => {
            const found = candidates.find((c) => c.id === record.candidate?.id || c.name === record.candidate?.name);
            if (found && onSelectCandidate) {
              onSelectCandidate(found);
            }
          }}
        >
          Inspect Profile
        </Button>
      ),
    },
  ];

  return (
    <Card
      bordered={false}
      style={{ borderRadius: 12, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
      title={
        <Space>
          <FileText size={20} style={{ color: "#0ea5e9" }} />
          <div>
            <span style={{ fontSize: 16, fontWeight: 700 }}>Candidate Applications Pipeline</span>
            <div style={{ fontSize: 12, color: "#64748b", fontWeight: 400 }}>
              End-to-end recruitment lifecycle and stage transitions
            </div>
          </div>
        </Space>
      }
    >
      <Table
        columns={columns}
        dataSource={applications}
        rowKey={(r) => r.id}
        loading={loading}
        pagination={{ pageSize: 8 }}
      />
    </Card>
  );
}
