import React, { useState } from "react";
import { Modal, Upload, Button, Select, Space, Progress, Tag, Typography, message, List } from "antd";
import { InboxOutlined, CheckCircleFilled, FileTextOutlined } from "@ant-design/icons";
import { Upload as LucideUpload, Layers, CheckCircle2, AlertCircle } from "lucide-react";
import { api } from "../api";

const { Text, Title } = Typography;

export function BulkResumeUploadModal({ open, onClose, onRefreshCandidates, clients = [] }) {
  const [fileList, setFileList] = useState([]);
  const [selectedClient, setSelectedClient] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [resultSummary, setResultSummary] = useState(null);

  const handleUploadChange = ({ fileList: newFileList }) => {
    setFileList(newFileList);
  };

  const handleStartImport = async () => {
    if (fileList.length === 0) {
      message.warning("Please select at least one resume file to upload.");
      return;
    }

    setIsProcessing(true);
    setProgress(15);

    try {
      const rawFiles = fileList.map((f) => f.originFileObj || f);
      setProgress(40);

      const result = await api.bulkUploadResumes(rawFiles, selectedClient);
      setProgress(100);

      setResultSummary(result);
      message.success(`Successfully imported ${result.succeededCount || fileList.length} candidate(s)!`);
      if (onRefreshCandidates) {
        onRefreshCandidates();
      }
    } catch (err) {
      console.error("Bulk upload failed:", err);
      message.error("Failed to process bulk upload: " + (err.message || "Unknown error"));
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReset = () => {
    setFileList([]);
    setProgress(0);
    setResultSummary(null);
  };

  const handleModalClose = () => {
    handleReset();
    onClose();
  };

  return (
    <Modal
      title={
        <Space>
          <Layers size={18} style={{ color: "#4f46e5" }} />
          <span style={{ fontWeight: 700 }}>Bulk Resume Upload Pipeline</span>
        </Space>
      }
      open={open}
      onCancel={handleModalClose}
      footer={null}
      width={680}
      destroyOnClose
    >
      <div style={{ padding: "8px 0" }}>
        <Text type="secondary" style={{ fontSize: 13, display: "block", marginBottom: 16 }}>
          Batch upload candidate resumes (PDF, DOCX, TXT). Each file will be parsed by Apache PDFBox/OCR,
          extracting skills, contact info, and experience directly into your talent database.
        </Text>

        {!resultSummary ? (
          <div>
            {/* Client selector */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6, color: "#334155" }}>
                Assign Ingested Candidates to Client (Optional):
              </label>
              <Select
                placeholder="-- General Talent Pool (No Client) --"
                style={{ width: "100%" }}
                allowClear
                value={selectedClient}
                onChange={(val) => setSelectedClient(val)}
              >
                <Select.Option value="">-- General Talent Pool (Unassigned) --</Select.Option>
                {clients.map((c) => (
                  <Select.Option key={c.id} value={c.id}>
                    {c.name} ({c.industry || "General"})
                  </Select.Option>
                ))}
              </Select>
            </div>

            {/* Dragger */}
            <Upload.Dragger
              multiple
              beforeUpload={() => false}
              fileList={fileList}
              onChange={handleUploadChange}
              accept=".pdf,.doc,.docx,.txt"
              style={{
                background: "#f8fafc",
                borderColor: "#c7d2fe",
                borderRadius: 10,
                padding: "24px 16px",
              }}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined style={{ color: "#4f46e5", fontSize: 42 }} />
              </p>
              <p className="ant-upload-text" style={{ fontWeight: 600, color: "#1e293b" }}>
                Click or drag resume files to this area to queue for batch ingestion
              </p>
              <p className="ant-upload-hint" style={{ fontSize: 12, color: "#64748b" }}>
                Supports batch uploading multiple PDFs or Word resumes simultaneously (up to 50MB per file).
              </p>
            </Upload.Dragger>

            {isProcessing && (
              <div style={{ marginTop: 20 }}>
                <Progress percent={progress} status="active" strokeColor="#4f46e5" />
                <div style={{ textAlign: "center", fontSize: 12, color: "#64748b", marginTop: 6 }}>
                  Extracting text, running parser, and generating candidate profiles...
                </div>
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 24 }}>
              <Button onClick={handleModalClose} disabled={isProcessing}>
                Cancel
              </Button>
              <Button
                type="primary"
                icon={<LucideUpload size={14} style={{ marginRight: 4 }} />}
                style={{ background: "#4f46e5", borderColor: "#4f46e5" }}
                onClick={handleStartImport}
                loading={isProcessing}
                disabled={fileList.length === 0}
              >
                Ingest {fileList.length} Resume{fileList.length !== 1 ? "s" : ""}
              </Button>
            </div>
          </div>
        ) : (
          <div style={{ textAlign: "center", padding: "16px 0" }}>
            <CheckCircle2 size={48} color="#16a34a" style={{ margin: "0 auto 12px" }} />
            <Title level={4} style={{ color: "#15803d", margin: "0 0 8px" }}>
              Batch Resume Ingestion Complete!
            </Title>
            <Text type="secondary">
              Processed {resultSummary.totalReceived || fileList.length} file(s) — successfully created{" "}
              <strong>{resultSummary.succeededCount || fileList.length}</strong> new candidate profiles in the database.
            </Text>

            <div style={{ display: "flex", justifyContent: "center", gap: 12, marginTop: 24 }}>
              <Button onClick={handleReset}>Upload More Resumes</Button>
              <Button type="primary" onClick={handleModalClose} style={{ background: "#4f46e5" }}>
                View In Candidate Database
              </Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}

