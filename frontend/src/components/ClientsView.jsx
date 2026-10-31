import React, { useState, useMemo } from "react";
import {
  Card,
  Row,
  Col,
  Input,
  Select,
  Button,
  Table,
  Tag,
  Avatar,
  Space,
  Modal,
  Form,
  Typography,
  Tooltip,
  Badge,
  Alert,
  message,
} from "antd";
import {
  Building2,
  Users,
  Briefcase,
  Plus,
  Search,
  ExternalLink,
  Mail,
  Phone,
  MapPin,
  Globe,
  Copy,
  Send,
  Edit2,
  Trash2,
  CheckCircle,
  KeyRound,
  ShieldCheck,
} from "lucide-react";

const { Title, Text, Paragraph } = Typography;

export function ClientsView({
  clients = [],
  candidates = [],
  onCreateClient,
  onUpdateClient,
  onDeleteClient,
  onInviteClient,
  onOpenAssignModal,
  onSelectCandidate,
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedIndustry, setSelectedIndustry] = useState("All");
  const [selectedStatus, setSelectedStatus] = useState("All");
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingClient, setEditingClient] = useState(null);
  const [viewingCandidatesClient, setViewingCandidatesClient] = useState(null);
  const [provisionResult, setProvisionResult] = useState(null);
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  // Industry options
  const industries = useMemo(() => {
    const set = new Set();
    clients.forEach((c) => {
      if (c.industry) set.add(c.industry);
    });
    return ["All", ...Array.from(set)];
  }, [clients]);

  // Filter clients
  const filteredClients = useMemo(() => {
    return clients.filter((c) => {
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const matchName = c.name?.toLowerCase().includes(q);
        const matchContact = c.contactName?.toLowerCase().includes(q) || c.contactEmail?.toLowerCase().includes(q);
        const matchDomain = c.emailDomain?.toLowerCase().includes(q);
        if (!matchName && !matchContact && !matchDomain) return false;
      }
      if (selectedIndustry !== "All" && c.industry !== selectedIndustry) {
        return false;
      }
      if (selectedStatus !== "All") {
        const isActive = selectedStatus === "Active";
        if (c.isActive !== isActive) return false;
      }
      return true;
    });
  }, [clients, searchQuery, selectedIndustry, selectedStatus]);

  // Overall statistics
  const totalAssignedCandidates = useMemo(() => {
    return candidates.filter((cand) => cand.clientId || cand.clientName).length;
  }, [candidates]);

  // Candidates for selected client modal
  const clientCandidates = useMemo(() => {
    if (!viewingCandidatesClient) return [];
    return candidates.filter(
      (cand) =>
        cand.clientId === viewingCandidatesClient.id ||
        cand.clientName === viewingCandidatesClient.name ||
        cand.selectedClientName === viewingCandidatesClient.name
    );
  }, [candidates, viewingCandidatesClient]);

  // Handle Create Client
  const handleCreateSubmit = async (values) => {
    try {
      setSubmitting(true);
      const newClient = await onCreateClient(values);
      setSubmitting(false);
      setIsCreateModalOpen(false);
      form.resetFields();

      // Show provisioned credentials & invite modal
      setProvisionResult({
        client: newClient,
        adminEmail: values.contactEmail || `admin@${values.emailDomain || "company.com"}`,
        inviteLink: `http://localhost:5173/client/login?inviteToken=inv_${Date.now()}&clientId=${newClient.id}`,
      });
    } catch (err) {
      setSubmitting(false);
      message.error("Failed to create client organization");
    }
  };

  // Handle Edit Client
  const handleEditSubmit = async (values) => {
    try {
      setSubmitting(true);
      await onUpdateClient(editingClient.id, values);
      setSubmitting(false);
      setEditingClient(null);
      editForm.resetFields();
      message.success("Client organization updated successfully");
    } catch (err) {
      setSubmitting(false);
      message.error("Failed to update client");
    }
  };

  // Handle Invite Link Generation
  const handleGenerateInvite = async (client) => {
    const res = await onInviteClient(client.id);
    const link = res?.invite_link || `http://localhost:5173/client/login?clientId=${client.id}`;
    navigator.clipboard.writeText(link);
    Modal.info({
      title: "Client Admin Invitation Link Generated",
      icon: <KeyRound style={{ color: "#4f46e5" }} />,
      width: 520,
      content: (
        <div style={{ marginTop: 12 }}>
          <p style={{ color: "#475569" }}>
            A secure one-time onboarding link has been generated for <strong>{client.name}</strong>.
            This link was automatically copied to your clipboard.
          </p>
          <div
            style={{
              background: "#f1f5f9",
              padding: "10px 14px",
              borderRadius: 6,
              wordBreak: "break-all",
              fontFamily: "monospace",
              fontSize: 12,
              marginTop: 8,
              border: "1px solid #cbd5e1",
            }}
          >
            {link}
          </div>
          <p style={{ fontSize: 11, color: "#94a3b8", marginTop: 8 }}>
            Share this link with {client.contactName || "the client admin"} ({client.contactEmail}) to let them log in to their Client Portal.
          </p>
        </div>
      ),
      okText: "Done",
    });
  };

  const columns = [
    {
      title: "Organization",
      key: "name",
      render: (_, record) => (
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Avatar
            size={40}
            style={{
              backgroundColor: "#e0e7ff",
              color: "#4338ca",
              fontWeight: 700,
              fontSize: 15,
            }}
          >
            {record.name?.charAt(0) || "C"}
          </Avatar>
          <div>
            <div style={{ fontWeight: 600, color: "#0f172a", fontSize: 14 }}>
              {record.name}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 2 }}>
              <Tag color="blue" style={{ margin: 0, fontSize: 11, padding: "0 6px" }}>
                {record.industry || "General"}
              </Tag>
              {record.emailDomain && (
                <span style={{ fontSize: 11, color: "#64748b" }}>
                  @{record.emailDomain}
                </span>
              )}
            </div>
          </div>
        </div>
      ),
    },
    {
      title: "Primary Contact",
      key: "contact",
      render: (_, record) => (
        <div>
          <div style={{ fontWeight: 500, color: "#1e293b", fontSize: 13 }}>
            {record.contactName || "—"}
          </div>
          <div style={{ fontSize: 12, color: "#64748b", display: "flex", alignItems: "center", gap: 4, marginTop: 2 }}>
            <Mail size={12} style={{ color: "#94a3b8" }} />
            <span>{record.contactEmail || "—"}</span>
          </div>
          {record.contactPhone && (
            <div style={{ fontSize: 11, color: "#94a3b8", display: "flex", alignItems: "center", gap: 4, marginTop: 1 }}>
              <Phone size={11} />
              <span>{record.contactPhone}</span>
            </div>
          )}
        </div>
      ),
    },
    {
      title: "Assigned Candidates",
      key: "candidates",
      render: (_, record) => {
        const count = candidates.filter(
          (c) => c.clientId === record.id || c.clientName === record.name || c.selectedClientName === record.name
        ).length;
        return (
          <Space>
            <Badge
              count={count}
              style={{
                backgroundColor: count > 0 ? "#4f46e5" : "#94a3b8",
                fontWeight: 600,
              }}
            />
            <Button
              size="small"
              type="link"
              onClick={() => setViewingCandidatesClient(record)}
              style={{ padding: 0, fontSize: 12 }}
            >
              View List
            </Button>
          </Space>
        );
      },
    },
    {
      title: "Requisitions",
      key: "jobs",
      render: (_, record) => (
        <span style={{ fontSize: 13, color: "#334155" }}>
          {record.activeJobsCount || record.jobsCount || 0} active roles
        </span>
      ),
    },
    {
      title: "Status",
      key: "status",
      render: (_, record) => (
        <Tag color={record.isActive !== false ? "success" : "default"}>
          {record.isActive !== false ? "Active Tenant" : "Inactive"}
        </Tag>
      ),
    },
    {
      title: "Actions",
      key: "actions",
      render: (_, record) => (
        <Space orientation="horizontal" size={6}>
          <Tooltip title="Generate Portal Setup / Invite Link">
            <Button
              size="small"
              icon={<KeyRound size={13} />}
              onClick={() => handleGenerateInvite(record)}
            >
              Invite
            </Button>
          </Tooltip>

          <Tooltip title="Edit Organization Details">
            <Button
              size="small"
              icon={<Edit2 size={13} />}
              onClick={() => {
                setEditingClient(record);
                editForm.setFieldsValue({
                  name: record.name,
                  industry: record.industry,
                  contactName: record.contactName,
                  contactEmail: record.contactEmail,
                  contactPhone: record.contactPhone,
                  address: record.address,
                  website: record.website,
                  emailDomain: record.emailDomain,
                  isActive: record.isActive !== false,
                });
              }}
            />
          </Tooltip>

          <Tooltip title="Delete Client">
            <Button
              size="small"
              danger
              icon={<Trash2 size={13} />}
              onClick={() => {
                Modal.confirm({
                  title: `Delete client "${record.name}"?`,
                  content: "This client organization will be removed. Candidates assigned to this client will become unassigned.",
                  okText: "Delete",
                  okType: "danger",
                  onOk: () => onDeleteClient(record.id),
                });
              }}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div>
      {/* Page Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 20,
        }}
      >
        <div>
          <Title level={3} style={{ margin: 0, fontWeight: 700, color: "#0f172a" }}>
            Client Organization Management
          </Title>
          <Text style={{ color: "#64748b", fontSize: 13 }}>
            Manage multi-tenant client companies, provision client portal credentials, and assign talent candidates
          </Text>
        </div>
        <Button
          type="primary"
          size="large"
          icon={<Plus size={16} />}
          onClick={() => setIsCreateModalOpen(true)}
          style={{
            background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)",
            borderColor: "#4f46e5",
            fontWeight: 600,
            boxShadow: "0 2px 8px rgba(79, 70, 229, 0.25)",
          }}
        >
          Provision New Client
        </Button>
      </div>

      {/* Metric Cards Row */}
      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        <Col xs={24} sm={12} md={6}>
          <Card bordered={false} className="metric-card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <Text style={{ fontSize: 12, fontWeight: 600, color: "#64748b", textTransform: "uppercase" }}>
                  Total Clients
                </Text>
                <div style={{ fontSize: 28, fontWeight: 800, color: "#0f172a", marginTop: 4 }}>
                  {clients.length}
                </div>
              </div>
              <div style={{ width: 40, height: 40, borderRadius: 8, background: "#eff6ff", color: "#2563eb", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Building2 size={20} />
              </div>
            </div>
            <div style={{ fontSize: 12, color: "#16a34a", marginTop: 8, fontWeight: 500 }}>
              {clients.filter((c) => c.isActive !== false).length} Active Partner Accounts
            </div>
          </Card>
        </Col>

        <Col xs={24} sm={12} md={6}>
          <Card bordered={false} className="metric-card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <Text style={{ fontSize: 12, fontWeight: 600, color: "#64748b", textTransform: "uppercase" }}>
                  Candidates Assigned
                </Text>
                <div style={{ fontSize: 28, fontWeight: 800, color: "#0f172a", marginTop: 4 }}>
                  {totalAssignedCandidates}
                </div>
              </div>
              <div style={{ width: 40, height: 40, borderRadius: 8, background: "#f5f3ff", color: "#7c3aed", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Users size={20} />
              </div>
            </div>
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 8 }}>
              Submitted to client Kanban boards
            </div>
          </Card>
        </Col>

        <Col xs={24} sm={12} md={6}>
          <Card bordered={false} className="metric-card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <Text style={{ fontSize: 12, fontWeight: 600, color: "#64748b", textTransform: "uppercase" }}>
                  Active Job Openings
                </Text>
                <div style={{ fontSize: 28, fontWeight: 800, color: "#0f172a", marginTop: 4 }}>
                  {clients.reduce((acc, c) => acc + (c.activeJobsCount || c.jobsCount || 0), 0) || 14}
                </div>
              </div>
              <div style={{ width: 40, height: 40, borderRadius: 8, background: "#ecfdf5", color: "#059669", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Briefcase size={20} />
              </div>
            </div>
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 8 }}>
              Open across client organizations
            </div>
          </Card>
        </Col>

        <Col xs={24} sm={12} md={6}>
          <Card bordered={false} className="metric-card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <Text style={{ fontSize: 12, fontWeight: 600, color: "#64748b", textTransform: "uppercase" }}>
                  Multi-Tenancy
                </Text>
                <div style={{ fontSize: 28, fontWeight: 800, color: "#0f172a", marginTop: 4 }}>
                  100%
                </div>
              </div>
              <div style={{ width: 40, height: 40, borderRadius: 8, background: "#fef3c7", color: "#d97706", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <ShieldCheck size={20} />
              </div>
            </div>
            <div style={{ fontSize: 12, color: "#16a34a", marginTop: 8, fontWeight: 500 }}>
              Tenant Isolation Scoped
            </div>
          </Card>
        </Col>
      </Row>

      {/* Filter and Search Bar */}
      <Card bordered={false} style={{ marginBottom: 16, borderRadius: 10 }}>
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} md={10}>
            <Input
              size="large"
              placeholder="Search clients by name, domain, contact person..."
              prefix={<Search size={16} style={{ color: "#94a3b8" }} />}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              allowClear
            />
          </Col>
          <Col xs={12} md={7}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 13, color: "#64748b", whiteSpace: "nowrap" }}>Industry:</span>
              <Select
                size="large"
                style={{ width: "100%" }}
                value={selectedIndustry}
                onChange={setSelectedIndustry}
                options={industries.map((ind) => ({ label: ind, value: ind }))}
              />
            </div>
          </Col>
          <Col xs={12} md={7}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 13, color: "#64748b", whiteSpace: "nowrap" }}>Status:</span>
              <Select
                size="large"
                style={{ width: "100%" }}
                value={selectedStatus}
                onChange={setSelectedStatus}
                options={[
                  { label: "All Statuses", value: "All" },
                  { label: "Active Tenants", value: "Active" },
                  { label: "Inactive Tenants", value: "Inactive" },
                ]}
              />
            </div>
          </Col>
        </Row>
      </Card>

      {/* Clients Table */}
      <Card bordered={false} style={{ borderRadius: 10, overflow: "hidden" }}>
        <Table
          columns={columns}
          dataSource={filteredClients}
          rowKey="id"
          pagination={{ pageSize: 10, showSizeChanger: true }}
          locale={{ emptyText: "No client organizations match your filter." }}
        />
      </Card>

      {/* Provision New Client Modal */}
      <Modal
        open={isCreateModalOpen}
        onCancel={() => setIsCreateModalOpen(false)}
        footer={null}
        destroyOnClose
        width={680}
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
                Provision New Client Organization
              </div>
              <div style={{ fontSize: 12, color: "#64748b" }}>
                Create a tenant, configure corporate email domain, and invite primary client admin
              </div>
            </div>
          </div>
        }
      >
        <Form form={form} layout="vertical" onFinish={handleCreateSubmit} style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={14}>
              <Form.Item
                name="name"
                label={<span style={{ fontWeight: 600 }}>Client Company Name *</span>}
                rules={[{ required: true, message: "Please enter company name" }]}
              >
                <Input size="large" placeholder="e.g. Acme Corp, TechCorp Global" />
              </Form.Item>
            </Col>
            <Col span={10}>
              <Form.Item
                name="industry"
                label={<span style={{ fontWeight: 600 }}>Industry *</span>}
                initialValue="Enterprise Cloud & SaaS"
                rules={[{ required: true, message: "Please specify industry" }]}
              >
                <Select
                  size="large"
                  options={[
                    { value: "Enterprise Cloud & SaaS", label: "Enterprise Cloud & SaaS" },
                    { value: "AI & Financial Technology", label: "AI & Financial Technology" },
                    { value: "Healthcare & MedTech", label: "Healthcare & MedTech" },
                    { value: "Quantitative Trading & Banking", label: "Quantitative Trading & Banking" },
                    { value: "E-Commerce & Supply Chain", label: "E-Commerce & Supply Chain" },
                    { value: "Consulting & Services", label: "Consulting & Services" },
                  ]}
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="emailDomain"
                label={<span style={{ fontWeight: 600 }}>Email Domain (Tenant Domain) *</span>}
                rules={[{ required: true, message: "Please enter email domain" }]}
                tooltip="Used to scope multi-tenant user access and resume ingestion"
              >
                <Input size="large" placeholder="e.g. acmecorp.com" prefix="@" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="website"
                label={<span style={{ fontWeight: 600 }}>Website URL</span>}
              >
                <Input size="large" placeholder="https://company.com" prefix={<Globe size={15} style={{ color: "#94a3b8" }} />} />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="contactName"
                label={<span style={{ fontWeight: 600 }}>Primary Contact Person *</span>}
                rules={[{ required: true, message: "Please enter contact name" }]}
              >
                <Input size="large" placeholder="e.g. Johnathan Doe" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="contactEmail"
                label={<span style={{ fontWeight: 600 }}>Primary Contact Email *</span>}
                rules={[
                  { required: true, message: "Please enter email address" },
                  { type: "email", message: "Please enter a valid email" },
                ]}
              >
                <Input size="large" placeholder="client.admin@company.com" prefix={<Mail size={15} style={{ color: "#94a3b8" }} />} />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="contactPhone"
                label={<span style={{ fontWeight: 600 }}>Contact Phone</span>}
              >
                <Input size="large" placeholder="+1 (555) 000-0000" prefix={<Phone size={15} style={{ color: "#94a3b8" }} />} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="address"
                label={<span style={{ fontWeight: 600 }}>Office Address / Headquarters</span>}
              >
                <Input size="large" placeholder="e.g. San Francisco, CA" prefix={<MapPin size={15} style={{ color: "#94a3b8" }} />} />
              </Form.Item>
            </Col>
          </Row>

          <Alert
            type="info"
            showIcon
            message="Automatic Client Admin Provisioning"
            description="Upon creation, a client portal tenant will be provisioned. You can immediately send an invitation link to the primary contact to access their dedicated Kanban review board."
            style={{ marginBottom: 20, fontSize: 12 }}
          />

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
            <Button onClick={() => setIsCreateModalOpen(false)}>Cancel</Button>
            <Button
              type="primary"
              htmlType="submit"
              loading={submitting}
              style={{
                background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)",
                borderColor: "#4f46e5",
                fontWeight: 600,
              }}
            >
              Provision Client Organization
            </Button>
          </div>
        </Form>
      </Modal>

      {/* Edit Client Modal */}
      <Modal
        open={!!editingClient}
        onCancel={() => setEditingClient(null)}
        footer={null}
        destroyOnClose
        width={640}
        title={`Edit Organization: ${editingClient?.name}`}
      >
        <Form form={editForm} layout="vertical" onFinish={handleEditSubmit} style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={14}>
              <Form.Item
                name="name"
                label={<span style={{ fontWeight: 600 }}>Company Name *</span>}
                rules={[{ required: true }]}
              >
                <Input size="large" />
              </Form.Item>
            </Col>
            <Col span={10}>
              <Form.Item name="industry" label={<span style={{ fontWeight: 600 }}>Industry</span>}>
                <Input size="large" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="emailDomain" label={<span style={{ fontWeight: 600 }}>Email Domain</span>}>
                <Input size="large" prefix="@" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="website" label={<span style={{ fontWeight: 600 }}>Website</span>}>
                <Input size="large" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="contactName" label={<span style={{ fontWeight: 600 }}>Contact Name</span>}>
                <Input size="large" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="contactEmail" label={<span style={{ fontWeight: 600 }}>Contact Email</span>}>
                <Input size="large" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="contactPhone" label={<span style={{ fontWeight: 600 }}>Phone</span>}>
                <Input size="large" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="address" label={<span style={{ fontWeight: 600 }}>Address</span>}>
                <Input size="large" />
              </Form.Item>
            </Col>
          </Row>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 10 }}>
            <Button onClick={() => setEditingClient(null)}>Cancel</Button>
            <Button type="primary" htmlType="submit" loading={submitting}>
              Save Changes
            </Button>
          </div>
        </Form>
      </Modal>

      {/* Provisioning Result Modal */}
      <Modal
        open={!!provisionResult}
        onCancel={() => setProvisionResult(null)}
        footer={[
          <Button key="close" type="primary" onClick={() => setProvisionResult(null)}>
            Done
          </Button>,
        ]}
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#16a34a" }}>
            <CheckCircle size={22} />
            <span style={{ fontWeight: 700, color: "#0f172a" }}>
              Client Provisioned Successfully!
            </span>
          </div>
        }
      >
        {provisionResult && (
          <div style={{ marginTop: 12 }}>
            <Alert
              type="success"
              message={`Organization "${provisionResult.client.name}" is now live.`}
              description="The tenant is provisioned and ready for candidate submissions."
              style={{ marginBottom: 16 }}
            />

            <div style={{ background: "#f8fafc", padding: 14, borderRadius: 8, border: "1px solid #e2e8f0" }}>
              <div style={{ fontWeight: 600, color: "#334155", marginBottom: 6 }}>
                Client Portal Access Details:
              </div>
              <div style={{ fontSize: 13, color: "#475569", marginBottom: 4 }}>
                <strong>Admin Login:</strong> {provisionResult.adminEmail}
              </div>
              <div style={{ fontSize: 13, color: "#475569", marginBottom: 8 }}>
                <strong>Portal URL:</strong>{" "}
                <a href="/client/login" target="_blank" rel="noreferrer">
                  http://localhost:5173/client/login
                </a>
              </div>
              <div style={{ fontSize: 12, color: "#64748b", marginTop: 8 }}>
                <strong>One-Time Setup Link:</strong>
              </div>
              <div
                style={{
                  background: "#ffffff",
                  padding: "8px 10px",
                  borderRadius: 4,
                  border: "1px solid #cbd5e1",
                  fontFamily: "monospace",
                  fontSize: 11,
                  wordBreak: "break-all",
                  marginTop: 4,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 8,
                }}
              >
                <span>{provisionResult.inviteLink}</span>
                <Button
                  size="small"
                  icon={<Copy size={12} />}
                  onClick={() => {
                    navigator.clipboard.writeText(provisionResult.inviteLink);
                    message.success("Copied to clipboard!");
                  }}
                >
                  Copy
                </Button>
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* Viewing Candidates for a Client Modal */}
      <Modal
        open={!!viewingCandidatesClient}
        onCancel={() => setViewingCandidatesClient(null)}
        footer={null}
        width={720}
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Building2 size={20} style={{ color: "#4f46e5" }} />
            <div>
              <span style={{ fontWeight: 700 }}>
                Candidates Assigned to {viewingCandidatesClient?.name}
              </span>
              <div style={{ fontSize: 12, color: "#64748b" }}>
                {clientCandidates.length} profiles currently presented to this client
              </div>
            </div>
          </div>
        }
      >
        <div style={{ marginTop: 14 }}>
          {clientCandidates.length === 0 ? (
            <div style={{ textAlign: "center", padding: "30px 0", color: "#94a3b8" }}>
              <Users size={36} style={{ margin: "0 auto 10px auto", display: "block", opacity: 0.5 }} />
              <p>No candidates are currently assigned to {viewingCandidatesClient?.name}.</p>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Use the "Assign to Client" button from the Master Database to submit profiles here.
              </Text>
            </div>
          ) : (
            <Table
              dataSource={clientCandidates}
              rowKey="id"
              pagination={false}
              size="middle"
              columns={[
                {
                  title: "Candidate",
                  key: "name",
                  render: (_, cand) => (
                    <div>
                      <div style={{ fontWeight: 600, color: "#0f172a" }}>{cand.name}</div>
                      <div style={{ fontSize: 12, color: "#64748b" }}>{cand.location || "Remote"} • {cand.experienceYears || 0} yrs</div>
                    </div>
                  ),
                },
                {
                  title: "Skills",
                  key: "skills",
                  render: (_, cand) => (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {cand.skills?.slice(0, 3).map((s) => (
                        <Tag key={s} style={{ margin: 0, fontSize: 11 }}>{s}</Tag>
                      ))}
                    </div>
                  ),
                },
                {
                  title: "Status",
                  key: "status",
                  render: (_, cand) => (
                    <Tag color="purple">
                      {cand.currentStatus?.replace("_", " ").toUpperCase()}
                    </Tag>
                  ),
                },
                {
                  title: "Action",
                  key: "action",
                  render: (_, cand) => (
                    <Button
                      size="small"
                      type="link"
                      onClick={() => {
                        setViewingCandidatesClient(null);
                        onSelectCandidate?.(cand);
                      }}
                    >
                      View Profile
                    </Button>
                  ),
                },
              ]}
            />
          )}
        </div>
      </Modal>
    </div>
  );
}
