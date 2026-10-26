import React, { useState, useEffect } from "react";
import { Table, Tag, Space, Typography, Button, Card, Modal, Form, Input, InputNumber, Select, message } from "antd";
import { Briefcase, PlusCircle, MapPin, Building, Users } from "lucide-react";
import { api } from "../api";

const { Title, Text } = Typography;

export function JobsView() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [form] = Form.useForm();

  const loadJobs = async () => {
    setLoading(true);
    try {
      const data = await api.getJobs();
      if (Array.isArray(data) && data.length > 0) {
        setJobs(data);
      } else {
        // Fallback demo jobs
        setJobs([
          {
            id: "job-1",
            title: "Senior Java / Spring Boot Engineer",
            department: "Engineering",
            location: "Bangalore (Hybrid)",
            employment_type: "FULL_TIME",
            openings_count: 3,
            salary_lpa: 28,
            experience_required: 5,
            status: "OPEN",
            company_name: "FinTech Platform",
          },
          {
            id: "job-2",
            title: "Full Stack React Developer",
            department: "Frontend",
            location: "Remote",
            employment_type: "FULL_TIME",
            openings_count: 2,
            salary_lpa: 22,
            experience_required: 4,
            status: "OPEN",
            company_name: "CloudScale Inc",
          },
          {
            id: "job-3",
            title: "DevOps & Infrastructure Lead",
            department: "Cloud Ops",
            location: "Hyderabad",
            employment_type: "FULL_TIME",
            openings_count: 1,
            salary_lpa: 35,
            experience_required: 7,
            status: "OPEN",
            company_name: "Enterprise Solutions",
          },
          {
            id: "job-4",
            title: "QA Automation Engineer",
            department: "Quality Assurance",
            location: "Pune",
            employment_type: "FULL_TIME",
            openings_count: 2,
            salary_lpa: 16,
            experience_required: 3,
            status: "CLOSED",
            company_name: "LogiTech Systems",
          },
        ]);
      }
    } catch (err) {
      console.error("Failed to load jobs", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJobs();
  }, []);

  const handleCreateJob = async (values) => {
    try {
      await api.createJob(values);
      message.success(`Job requisition "${values.title}" created successfully!`);
      setIsAddModalOpen(false);
      form.resetFields();
      loadJobs();
    } catch (err) {
      message.error("Failed to create job requisition");
    }
  };

  const columns = [
    {
      title: "Job Title",
      dataIndex: "title",
      key: "title",
      render: (text, record) => (
        <Space direction="vertical" size={2}>
          <Text strong style={{ fontSize: 14, color: "#1e293b" }}>
            {text}
          </Text>
          <Text orientation="horizontal" type="secondary" style={{ fontSize: 12 }}>
            <Building size={12} style={{ display: "inline", marginRight: 4 }} />
            {record.company_name || "Enterprise ATS"}
          </Text>
        </Space>
      ),
    },
    {
      title: "Department",
      dataIndex: "department",
      key: "department",
      render: (dept) => <Tag color="blue">{dept || "General"}</Tag>,
    },
    {
      title: "Location",
      dataIndex: "location",
      key: "location",
      render: (loc) => (
        <Space size={4}>
          <MapPin size={13} style={{ color: "#64748b" }} />
          <span>{loc || "Remote"}</span>
        </Space>
      ),
    },
    {
      title: "Openings",
      dataIndex: "openings_count",
      key: "openings_count",
      render: (count) => (
        <Space size={4}>
          <Users size={13} style={{ color: "#64748b" }} />
          <Text strong>{count || 1}</Text>
        </Space>
      ),
    },
    {
      title: "Comp / Exp",
      key: "compensation",
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text strong style={{ color: "#10b981", fontSize: 13 }}>
            {record.salary_lpa ? `₹${record.salary_lpa} LPA` : "Not disclosed"}
          </Text>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {record.experience_required ? `${record.experience_required}+ yrs exp` : "Entry level"}
          </Text>
        </Space>
      ),
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (status) => (
        <Tag color={status === "OPEN" || status === "Active" ? "green" : "default"}>
          {status || "OPEN"}
        </Tag>
      ),
    },
  ];

  return (
    <div>
      <Card
        bordered={false}
        style={{ borderRadius: 12, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
        title={
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <Space>
              <Briefcase size={20} style={{ color: "#4f46e5" }} />
              <div>
                <span style={{ fontSize: 16, fontWeight: 700 }}>Job Requisitions</span>
                <div style={{ fontSize: 12, color: "#64748b", fontWeight: 400 }}>
                  Active job openings across all client accounts
                </div>
              </div>
            </Space>
            <Button
              type="primary"
              icon={<PlusCircle size={15} style={{ marginRight: 4 }} />}
              onClick={() => setIsAddModalOpen(true)}
              style={{ background: "#4f46e5" }}
            >
              Post Job Opening
            </Button>
          </div>
        }
      >
        <Table
          columns={columns}
          dataSource={jobs}
          rowKey={(r) => r.id || r.title}
          loading={loading}
          pagination={{ pageSize: 8 }}
        />
      </Card>

      {/* Add Job Modal */}
      <Modal
        title="Post New Job Requisition"
        open={isAddModalOpen}
        onCancel={() => setIsAddModalOpen(false)}
        footer={null}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleCreateJob} style={{ marginTop: 16 }}>
          <Form.Item name="title" label="Job Title" rules={[{ required: true, message: "Enter job title" }]}>
            <Input placeholder="e.g. Senior Java / Spring Boot Engineer" />
          </Form.Item>
          <Form.Item name="companyName" label="Client / Company Name" initialValue="Enterprise ATS">
            <Input placeholder="e.g. Acme Corp" />
          </Form.Item>
          <Form.Item name="department" label="Department" initialValue="Engineering">
            <Select>
              <Select.Option value="Engineering">Engineering</Select.Option>
              <Select.Option value="Frontend">Frontend</Select.Option>
              <Select.Option value="Product">Product</Select.Option>
              <Select.Option value="Cloud Ops">Cloud Ops</Select.Option>
              <Select.Option value="Design">Design</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="location" label="Location" initialValue="Bangalore">
            <Input placeholder="e.g. Bangalore, Remote, Hybrid" />
          </Form.Item>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <Form.Item name="salaryLpa" label="Salary (LPA)" initialValue={24}>
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="experienceRequired" label="Min Experience (Years)" initialValue={4}>
              <InputNumber min={0} style={{ width: "100%" }} />
            </Form.Item>
          </div>
          <Form.Item name="openingsCount" label="Openings Count" initialValue={1}>
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0, textAlign: "right" }}>
            <Space>
              <Button onClick={() => setIsAddModalOpen(false)}>Cancel</Button>
              <Button type="primary" htmlType="submit" style={{ background: "#4f46e5" }}>
                Create Requisition
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
