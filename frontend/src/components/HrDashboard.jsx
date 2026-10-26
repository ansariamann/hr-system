import React, { useState, useMemo } from "react";
import {
  Card,
  Row,
  Col,
  Input,
  Select,
  InputNumber,
  Table,
  Tag,
  Avatar,
  Space,
  Button,
  Typography,
  Tooltip,
} from "antd";
import {
  Search,
  MapPin,
  Briefcase,
  ShieldAlert,
  FileText,
  Calendar,
  Send,
  Eye,
  RotateCcw,
  UserCheck,
  Building2,
} from "lucide-react";

const { Text } = Typography;

export function HrDashboard({
  candidates,
  clients = [],
  onReviewCandidate,
  onScheduleInterview,
  onSendToClient,
  onOpenAssignModal,
  onToggleBlacklist,
  onResetData,
  onSelectCandidate,
}) {
  // Search and filter states matching master/list.tsx
  const [nameSearch, setNameSearch] = useState("");
  const [skillSearch, setSkillSearch] = useState("");
  const [selectedCity, setSelectedCity] = useState("All");
  const [selectedClient, setSelectedClient] = useState("All");
  const [maxExperience, setMaxExperience] = useState(null);
  const [excludeLeavers, setExcludeLeavers] = useState(true);
  const [selectedSkillPill, setSelectedSkillPill] = useState("All");

  // Extract unique locations
  const allLocations = useMemo(() => {
    const set = new Set();
    candidates.forEach((c) => {
      if (c.location) set.add(c.location);
    });
    return ["All", ...Array.from(set)];
  }, [candidates]);

  // Extract top skills for quick facet pills
  const topSkills = useMemo(() => {
    const map = new Map();
    candidates.forEach((c) => {
      c.skills?.forEach((s) => {
        map.set(s, (map.get(s) || 0) + 1);
      });
    });
    const sorted = Array.from(map.entries())
      .sort((a, b) => b[1] - a[1])
      .map((entry) => entry[0]);
    return ["All", ...sorted.slice(0, 10)];
  }, [candidates]);

  // Filtered candidate list based on master database rules
  const filteredCandidates = useMemo(() => {
    return candidates.filter((cand) => {
      // Leaver Exclusion Policy
      if (excludeLeavers && cand.isBlacklisted) {
        return false;
      }

      // Name & Email filter
      if (nameSearch) {
        const q = nameSearch.toLowerCase();
        const matchesName = cand.name?.toLowerCase().includes(q);
        const matchesEmail = cand.email?.toLowerCase().includes(q);
        if (!matchesName && !matchesEmail) return false;
      }

      // Skills input filter
      if (skillSearch) {
        const q = skillSearch.toLowerCase();
        const matchesSkill = cand.skills?.some((s) => s.toLowerCase().includes(q));
        if (!matchesSkill) return false;
      }

      // Quick facet skill pill
      if (selectedSkillPill !== "All") {
        if (!cand.skills?.some((s) => s.toLowerCase() === selectedSkillPill.toLowerCase())) {
          return false;
        }
      }

      // City filter
      if (selectedCity !== "All") {
        if (!cand.location?.toLowerCase().includes(selectedCity.toLowerCase())) {
          return false;
        }
      }

      // Client filter
      if (selectedClient !== "All") {
        if (selectedClient === "Unassigned") {
          if (cand.clientId || cand.clientName || cand.selectedClientName) return false;
        } else {
          const match =
            cand.clientName === selectedClient ||
            cand.selectedClientName === selectedClient ||
            cand.clientId === selectedClient;
          if (!match) return false;
        }
      }

      // Max Experience filter
      if (maxExperience !== null && maxExperience !== undefined && maxExperience !== "") {
        if (cand.experienceYears && cand.experienceYears > Number(maxExperience)) {
          return false;
        }
      }

      return true;
    });
  }, [candidates, nameSearch, skillSearch, selectedSkillPill, selectedCity, selectedClient, maxExperience, excludeLeavers]);

  const getStatusTag = (status, isBlacklisted) => {
    if (isBlacklisted) {
      return <Tag color="error">⚠️ LEAVER (EXCLUDED)</Tag>;
    }
    switch (status) {
      case "pool":
        return <Tag color="default">POOL</Tag>;
      case "submitted":
        return <Tag color="cyan">SUBMITTED</Tag>;
      case "interview_scheduled":
        return <Tag color="purple">INTERVIEW</Tag>;
      case "selected":
        return <Tag color="blue">SELECTED</Tag>;
      case "joined":
      case "hired":
        return <Tag color="green">HIRED</Tag>;
      case "left_company":
        return <Tag color="red">LEFT COMPANY</Tag>;
      default:
        return <Tag color="default">{status ? status.toUpperCase() : "POOL"}</Tag>;
    }
  };

  const columns = [
    {
      title: "Candidate",
      key: "candidate",
      render: (_, record) => {
        const initial = record.name ? record.name[0].toUpperCase() : "C";
        return (
          <Space>
            <Avatar
              style={{
                backgroundColor: record.isBlacklisted ? "#ef4444" : "#4f46e5",
                fontWeight: 600,
                cursor: "pointer",
              }}
              onClick={() => onSelectCandidate && onSelectCandidate(record)}
            >
              {initial}
            </Avatar>
            <Space direction="vertical" size={0}>
              <div
                style={{
                  fontWeight: 600,
                  fontSize: 14,
                  color: record.isBlacklisted ? "#ef4444" : "#0f172a",
                  cursor: "pointer",
                }}
                onClick={() => onSelectCandidate && onSelectCandidate(record)}
              >
                {record.name}
              </div>
              <div style={{ fontSize: 12, color: "#64748b" }}>
                {record.email} {record.phone ? `• ${record.phone}` : ""}
              </div>
            </Space>
          </Space>
        );
      },
    },
    {
      title: "Skills & Tech Stack",
      dataIndex: "skills",
      key: "skills",
      render: (skills) => {
        const list = Array.isArray(skills) ? skills : [];
        if (list.length === 0) return <Text type="secondary">—</Text>;
        const displayed = list.slice(0, 3);
        const remaining = list.length - 3;
        return (
          <Space wrap size={[4, 4]}>
            {displayed.map((skill) => (
              <Tag key={skill} color="geekblue" style={{ fontSize: 11, borderRadius: 4 }}>
                {skill}
              </Tag>
            ))}
            {remaining > 0 && (
              <Tag style={{ fontSize: 11, borderRadius: 4 }}>+{remaining}</Tag>
            )}
          </Space>
        );
      },
    },
    {
      title: "Location",
      dataIndex: "location",
      key: "location",
      render: (loc) => (
        <Space size={4}>
          <MapPin size={13} style={{ color: "#64748b" }} />
          <Text style={{ fontSize: 13 }}>{loc || "Remote"}</Text>
        </Space>
      ),
    },
    {
      title: "Experience / CTC",
      key: "exp_ctc",
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text strong style={{ fontSize: 13, color: "#1e293b" }}>
            {record.experienceYears ? `${record.experienceYears} yrs exp` : "—"}
          </Text>
          <Text style={{ fontSize: 12, color: "#10b981", fontWeight: 600 }}>
            {record.ctcCurrent ? `₹${(record.ctcCurrent / 100000).toFixed(1)} LPA` : "Not disclosed"}
          </Text>
        </Space>
      ),
    },
    {
      title: "Assigned Client",
      key: "client",
      render: (_, record) => {
        const clientName = record.selectedClientName || record.clientName;
        return clientName ? (
          <Tag
            color="blue"
            icon={<Building2 size={11} style={{ marginRight: 3, verticalAlign: "middle" }} />}
            style={{ borderRadius: 4, fontSize: 11, padding: "1px 6px" }}
          >
            {clientName}
          </Tag>
        ) : (
          <Tag style={{ borderRadius: 4, fontSize: 11, color: "#94a3b8" }}>
            Unassigned
          </Tag>
        );
      },
    },
    {
      title: "Status",
      key: "status",
      render: (_, record) => getStatusTag(record.currentStatus, record.isBlacklisted),
    },
    {
      title: "Actions",
      key: "actions",
      align: "right",
      render: (_, record) => (
        <Space size={4}>
          <Tooltip title="View Candidate Profile">
            <Button
              size="small"
              icon={<Eye size={13} />}
              onClick={() => onSelectCandidate && onSelectCandidate(record)}
            />
          </Tooltip>
          <Tooltip title="Split-Screen Document Review">
            <Button
              size="small"
              icon={<FileText size={13} />}
              onClick={() => onReviewCandidate(record)}
            >
              Review
            </Button>
          </Tooltip>
          <Tooltip title="Schedule Direct Interview">
            <Button
              size="small"
              type="primary"
              icon={<Calendar size={13} />}
              onClick={() => onScheduleInterview(record)}
              style={{ background: "#4f46e5" }}
            >
              Interview
            </Button>
          </Tooltip>
          <Tooltip title="Assign Profile to Client Portal">
            <Button
              size="small"
              icon={<Send size={13} />}
              onClick={() => {
                if (onOpenAssignModal) {
                  onOpenAssignModal(record);
                } else {
                  onSendToClient(record.id);
                }
              }}
              style={{ color: "#4f46e5", borderColor: "#c7d2fe" }}
            >
              Assign
            </Button>
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        bordered={false}
        style={{
          borderRadius: 12,
          boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
          marginBottom: 20,
        }}
      >
        {/* Header & Reset Button */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 20,
          }}
        >
          <div>
            <h2 style={{ fontSize: "1.15rem", margin: 0, fontWeight: 700, color: "#0f172a" }}>
              Master Candidate Database
            </h2>
            <Text type="secondary" style={{ fontSize: 12 }}>
              High-speed multi-faceted talent search with JSONB skills & automatic compliance exclusion
            </Text>
          </div>
          <Button
            icon={<RotateCcw size={14} style={{ marginRight: 4 }} />}
            size="small"
            onClick={onResetData}
          >
            Reset Demo DB
          </Button>
        </div>

        {/* Multi-Filter Search Bar matching master/list.tsx */}
        <div style={{ background: "#f8fafc", padding: 16, borderRadius: 8, marginBottom: 16 }}>
          <Row gutter={[12, 12]}>
            <Col xs={24} sm={12} md={5}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, color: "#475569" }}>
                Candidate Name / Email
              </div>
              <Input
                placeholder="Search by name or email..."
                prefix={<Search size={14} style={{ color: "#94a3b8" }} />}
                value={nameSearch}
                onChange={(e) => setNameSearch(e.target.value)}
                allowClear
              />
            </Col>

            <Col xs={24} sm={12} md={5}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, color: "#475569" }}>
                Skills (e.g. Java, React, Python)
              </div>
              <Input
                placeholder="Search skills..."
                prefix={<Search size={14} style={{ color: "#94a3b8" }} />}
                value={skillSearch}
                onChange={(e) => setSkillSearch(e.target.value)}
                allowClear
              />
            </Col>

            <Col xs={24} sm={12} md={5}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, color: "#475569" }}>
                Client Organization
              </div>
              <Select
                value={selectedClient}
                onChange={(val) => setSelectedClient(val)}
                style={{ width: "100%" }}
                showSearch
                filterOption={(input, option) =>
                  (option?.children ?? "").toLowerCase().includes(input.toLowerCase())
                }
              >
                <Select.Option value="All">All Clients</Select.Option>
                <Select.Option value="Unassigned">Unassigned Candidates</Select.Option>
                {clients.map((c) => (
                  <Select.Option key={c.id} value={c.name}>
                    {c.name}
                  </Select.Option>
                ))}
              </Select>
            </Col>

            <Col xs={24} sm={12} md={5}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, color: "#475569" }}>
                City / Location
              </div>
              <Select
                value={selectedCity}
                onChange={(val) => setSelectedCity(val)}
                style={{ width: "100%" }}
              >
                {allLocations.map((loc) => (
                  <Select.Option key={loc} value={loc}>
                    {loc}
                  </Select.Option>
                ))}
              </Select>
            </Col>

            <Col xs={24} sm={12} md={4}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, color: "#475569" }}>
                Max Exp (Yrs)
              </div>
              <InputNumber
                placeholder="e.g. 5"
                min={0}
                max={30}
                value={maxExperience}
                onChange={(val) => setMaxExperience(val)}
                style={{ width: "100%" }}
              />
            </Col>
          </Row>

          {/* Skill Pills & Leaver Policy Banner */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 12,
              marginTop: 14,
              paddingTop: 12,
              borderTop: "1px solid #e2e8f0",
            }}
          >
            {/* Quick Skill Filter Pills */}
            <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12, color: "#64748b", fontWeight: 600 }}>Top Skills:</span>
              {topSkills.map((s) => (
                <Tag
                  key={s}
                  color={selectedSkillPill === s ? "purple" : "default"}
                  style={{
                    cursor: "pointer",
                    borderRadius: 12,
                    padding: "2px 10px",
                    fontWeight: selectedSkillPill === s ? 600 : 400,
                  }}
                  onClick={() => setSelectedSkillPill(s)}
                >
                  {s}
                </Tag>
              ))}
            </div>

            {/* Leaver Exclusion Policy Banner */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                cursor: "pointer",
                padding: "6px 12px",
                borderRadius: 20,
                background: excludeLeavers ? "#fef2f2" : "#f1f5f9",
                border: `1px solid ${excludeLeavers ? "#fca5a5" : "#cbd5e1"}`,
              }}
              onClick={() => setExcludeLeavers(!excludeLeavers)}
              title="Per the Architecture Blueprint: Terminated former employees are automatically excluded from searches"
            >
              <ShieldAlert size={15} color={excludeLeavers ? "#ef4444" : "#64748b"} />
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: excludeLeavers ? "#b91c1c" : "#475569",
                }}
              >
                {excludeLeavers
                  ? "Policy: Ex-Employees Quarantined (ACTIVE)"
                  : "Audit Mode: Ex-Employees Included"}
              </span>
            </div>
          </div>
        </div>

        {/* Ant Design Candidates Table */}
        <Table
          columns={columns}
          dataSource={filteredCandidates}
          rowKey="id"
          pagination={{ pageSize: 10, showSizeChanger: true }}
        />
      </Card>
    </div>
  );
}
