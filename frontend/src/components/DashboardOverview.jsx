import React, { useMemo } from "react";
import { Row, Col, Typography, Card, List, Avatar, Space, Tag, Progress, Button } from "antd";
import {
  Users,
  FileText,
  CheckCircle,
  Briefcase,
  TrendingUp,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
  AlertTriangle,
  PlusCircle,
  Eye,
} from "lucide-react";

const { Title, Text } = Typography;

function StatsCard({ title, value, icon: Icon, trend, description, color = "#6366f1" }) {
  return (
    <Card
      bordered={false}
      style={{
        borderRadius: 12,
        boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
        background: "#ffffff",
        height: "100%",
      }}
      bodyStyle={{ padding: 20 }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 13, fontWeight: 500 }}>
          {title}
        </Text>
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            backgroundColor: `${color}15`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: color,
          }}
        >
          <Icon size={18} />
        </div>
      </div>
      <div>
        <div style={{ fontSize: 26, fontWeight: 700, color: "#0f172a", marginBottom: 4 }}>
          {value}
        </div>
        {(trend || description) && (
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
            {trend && (
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  fontWeight: 600,
                  color: trend.isPositive ? "#10b981" : "#ef4444",
                }}
              >
                {trend.isPositive ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                {Math.abs(trend.value)}%
              </span>
            )}
            {description && <Text type="secondary">{description}</Text>}
          </div>
        )}
      </div>
    </Card>
  );
}

export function DashboardOverview({
  candidates = [],
  jobs = [],
  applications = [],
  onNavigateTab,
  onOpenAddModal,
}) {
  const stats = useMemo(() => {
    const totalCandidates = candidates.length;
    const activeApps = applications.length || candidates.filter((c) => ["submitted", "interview_scheduled", "selected"].includes(c.currentStatus)).length;
    const hiredCount = candidates.filter((c) => ["joined", "hired"].includes(c.currentStatus)).length;
    const openPositions = jobs.length || 4;

    return [
      {
        title: "Total Candidates",
        value: totalCandidates.toLocaleString(),
        icon: Users,
        trend: { value: 14, isPositive: true },
        description: "vs last month",
        color: "#6366f1",
      },
      {
        title: "Active Pipeline",
        value: activeApps.toLocaleString(),
        icon: FileText,
        trend: { value: 8, isPositive: true },
        description: "currently processing",
        color: "#0ea5e9",
      },
      {
        title: "Hired Candidates",
        value: hiredCount.toLocaleString(),
        icon: CheckCircle,
        trend: { value: 5, isPositive: true },
        description: "joined this cycle",
        color: "#10b981",
      },
      {
        title: "Open Requisitions",
        value: openPositions.toLocaleString(),
        icon: Briefcase,
        description: "across departments",
        color: "#f59e0b",
      },
    ];
  }, [candidates, jobs, applications]);

  // Stage distribution
  const stageDistribution = useMemo(() => {
    const counts = {
      pool: 0,
      submitted: 0,
      interview_scheduled: 0,
      selected: 0,
      joined: 0,
      left_company: 0,
    };
    candidates.forEach((c) => {
      const s = c.currentStatus || "pool";
      if (counts[s] !== undefined) counts[s]++;
      else counts.pool++;
    });
    return counts;
  }, [candidates]);

  // Recent system / HR activities
  const activities = useMemo(() => {
    return [
      {
        user: "Aman Ansari",
        action: "scheduled interview for",
        target: candidates[0]?.name || "Alex Morgan",
        status: "Interview",
        statusColor: "purple",
        time: "15 mins ago",
      },
      {
        user: "Client Acme Corp",
        action: "accepted candidate profile",
        target: candidates[1]?.name || "David Chen",
        status: "Selected",
        statusColor: "green",
        time: "1 hour ago",
      },
      {
        user: "Ingestion Webhook",
        action: "parsed new resume for",
        target: candidates[2]?.name || "Sarah Jenkins",
        status: "New",
        statusColor: "blue",
        time: "2 hours ago",
      },
      {
        user: "System Policy",
        action: "quarantined ex-employee",
        target: "Leaver Profile",
        status: "Excluded",
        statusColor: "red",
        time: "4 hours ago",
      },
    ];
  }, [candidates]);

  return (
    <div style={{ padding: "0 0 24px 0" }}>
      {/* Page Title & Actions */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 20,
        }}
      >
        <div>
          <Title level={3} style={{ margin: 0, color: "#0f172a" }}>
            HR Recruitment Dashboard
          </Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            Overview of your enterprise talent acquisition pipeline and active requisitions
          </Text>
        </div>
        <Space>
          <Button
            type="primary"
            icon={<PlusCircle size={15} style={{ marginRight: 4 }} />}
            onClick={onOpenAddModal}
            style={{ background: "#4f46e5" }}
          >
            Add Candidate
          </Button>
          <Button
            icon={<Eye size={15} style={{ marginRight: 4 }} />}
            onClick={() => onNavigateTab("candidates")}
          >
            View Master DB
          </Button>
        </Space>
      </div>

      {/* Stats Metric Cards Grid */}
      <Row gutter={[16, 16]}>
        {stats.map((stat, index) => (
          <Col xs={24} sm={12} lg={6} key={index}>
            <StatsCard {...stat} />
          </Col>
        ))}
      </Row>

      {/* Main Content Row: Pipeline Distribution & Recent Activity */}
      <Row gutter={[16, 16]} style={{ marginTop: 20 }}>
        {/* Recruitment Pipeline Progress Breakdown */}
        <Col xs={24} lg={15}>
          <Card
            title={
              <Space>
                <TrendingUp size={18} style={{ color: "#4f46e5" }} />
                <span>Recruitment Pipeline Breakdown</span>
              </Space>
            }
            bordered={false}
            style={{ borderRadius: 12, boxShadow: "0 2px 8px rgba(0,0,0,0.06)", height: "100%" }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <Text strong style={{ fontSize: 13 }}>Talent Pool (Sourced)</Text>
                  <Text type="secondary">{stageDistribution.pool} candidates</Text>
                </div>
                <Progress
                  percent={Math.min(100, Math.round((stageDistribution.pool / (candidates.length || 1)) * 100))}
                  strokeColor="#64748b"
                />
              </div>

              <div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <Text strong style={{ fontSize: 13 }}>Submitted to Client Portal</Text>
                  <Text type="secondary">{stageDistribution.submitted} candidates</Text>
                </div>
                <Progress
                  percent={Math.min(100, Math.round((stageDistribution.submitted / (candidates.length || 1)) * 100))}
                  strokeColor="#0ea5e9"
                />
              </div>

              <div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <Text strong style={{ fontSize: 13 }}>Interviews Scheduled</Text>
                  <Text type="secondary">{stageDistribution.interview_scheduled} candidates</Text>
                </div>
                <Progress
                  percent={Math.min(100, Math.round((stageDistribution.interview_scheduled / (candidates.length || 1)) * 100))}
                  strokeColor="#8b5cf6"
                />
              </div>

              <div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <Text strong style={{ fontSize: 13 }}>Selected by Client</Text>
                  <Text type="secondary">{stageDistribution.selected} candidates</Text>
                </div>
                <Progress
                  percent={Math.min(100, Math.round((stageDistribution.selected / (candidates.length || 1)) * 100))}
                  strokeColor="#10b981"
                />
              </div>

              <div
                style={{
                  marginTop: 8,
                  padding: "12px 16px",
                  background: "#fef2f2",
                  borderRadius: 8,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <Space>
                  <AlertTriangle size={16} color="#ef4444" />
                  <Text style={{ fontSize: 12, color: "#991b1b" }}>
                    <strong>Leaver Exclusion Enforcement:</strong> {stageDistribution.left_company} former employee(s) quarantined.
                  </Text>
                </Space>
                <Tag color="error">Quarantined</Tag>
              </div>
            </div>
          </Card>
        </Col>

        {/* Recent Activity Feed */}
        <Col xs={24} lg={9}>
          <Card
            title={
              <Space>
                <Clock size={18} style={{ color: "#0ea5e9" }} />
                <span>Recent Activity</span>
              </Space>
            }
            bordered={false}
            style={{ borderRadius: 12, boxShadow: "0 2px 8px rgba(0,0,0,0.06)", height: "100%" }}
          >
            <List
              itemLayout="horizontal"
              dataSource={activities}
              renderItem={(item) => (
                <List.Item style={{ padding: "12px 0" }}>
                  <List.Item.Meta
                    avatar={
                      <Avatar
                        style={{
                          backgroundColor:
                            item.statusColor === "green"
                              ? "#10b981"
                              : item.statusColor === "purple"
                              ? "#8b5cf6"
                              : item.statusColor === "red"
                              ? "#ef4444"
                              : "#3b82f6",
                          color: "#fff",
                          fontWeight: 600,
                        }}
                      >
                        {item.user[0]}
                      </Avatar>
                    }
                    title={
                      <div style={{ fontSize: 13 }}>
                        <Text strong>{item.user}</Text>{" "}
                        <Text type="secondary">{item.action}</Text>{" "}
                        <Text strong style={{ color: "#1e293b" }}>
                          {item.target}
                        </Text>
                      </div>
                    }
                    description={
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
                        <Tag color={item.statusColor} style={{ fontSize: 11, borderRadius: 4 }}>
                          {item.status}
                        </Tag>
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          {item.time}
                        </Text>
                      </div>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
