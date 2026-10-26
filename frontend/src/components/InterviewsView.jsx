import React from "react";
import { Table, Tag, Space, Typography, Card, Button, Avatar } from "antd";
import { Calendar, Video, MapPin, Clock, PlusCircle } from "lucide-react";

const { Text } = Typography;

export function InterviewsView({ candidates = [], onScheduleInterview, onSelectCandidate }) {
  const interviewCandidates = candidates.filter(
    (c) => c.currentStatus === "interview_scheduled" || c.currentStatus === "selected"
  );

  const columns = [
    {
      title: "Candidate",
      key: "candidate",
      render: (_, record) => (
        <Space>
          <Avatar style={{ backgroundColor: "#8b5cf6" }}>
            {record.name ? record.name[0].toUpperCase() : "C"}
          </Avatar>
          <Space direction="vertical" size={0}>
            <Text strong style={{ fontSize: 14 }}>
              {record.name}
            </Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {record.email}
            </Text>
          </Space>
        </Space>
      ),
    },
    {
      title: "Role / Skills",
      dataIndex: "skills",
      key: "skills",
      render: (skills) => (
        <Space wrap>
          {(skills || []).slice(0, 3).map((s) => (
            <Tag key={s} color="geekblue">
              {s}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: "Interview Status",
      dataIndex: "currentStatus",
      key: "status",
      render: (status) => (
        <Tag color={status === "selected" ? "green" : "purple"}>
          {status === "selected" ? "SELECTED" : "INTERVIEW SCHEDULED"}
        </Tag>
      ),
    },
    {
      title: "Location / Mode",
      key: "location",
      render: (_, record) => (
        <Space size={4}>
          <Video size={13} style={{ color: "#64748b" }} />
          <span>Google Meet (Online)</span>
        </Space>
      ),
    },
    {
      title: "Actions",
      key: "actions",
      align: "right",
      render: (_, record) => (
        <Space size={6}>
          <Button size="small" onClick={() => onSelectCandidate(record)}>
            Inspect
          </Button>
          <Button
            size="small"
            type="primary"
            style={{ background: "#4f46e5" }}
            onClick={() => onScheduleInterview(record)}
          >
            Reschedule
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <Card
      bordered={false}
      style={{ borderRadius: 12, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
      title={
        <Space>
          <Calendar size={20} style={{ color: "#8b5cf6" }} />
          <div>
            <span style={{ fontSize: 16, fontWeight: 700 }}>Direct & Client Interviews</span>
            <div style={{ fontSize: 12, color: "#64748b", fontWeight: 400 }}>
              Candidates currently progressing through evaluation rounds
            </div>
          </div>
        </Space>
      }
    >
      <Table
        columns={columns}
        dataSource={interviewCandidates}
        rowKey="id"
        pagination={{ pageSize: 8 }}
        locale={{
          emptyText: "No interviews currently scheduled. Go to Master Database to schedule rounds.",
        }}
      />
    </Card>
  );
}
