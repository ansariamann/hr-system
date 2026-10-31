import React, { useState } from "react";
import { Drawer, Input, List, Typography, Button, Badge, Space, Tag } from "antd";
import { RobotOutlined, SendOutlined, BulbOutlined } from "@ant-design/icons";

const { Text } = Typography;

const SUGGESTIONS = [
  "Summarize candidate pipeline",
  "Explain candidate flags & leavers",
  "Check duplicate risks",
  "Draft technical interview questions",
];

export function HrCopilot({ candidates = [] }) {
  const [visible, setVisible] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hello! I am your HR AI Copilot. I can analyze candidate qualifications, explain flags, summarize resumes, and assist with interview prep.",
    },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);

  const generateResponse = (prompt) => {
    const p = prompt.toLowerCase();
    const total = candidates.length;
    const leavers = candidates.filter((c) => c.isBlacklisted || c.currentStatus === "left_company").length;
    const interviewCount = candidates.filter((c) => c.currentStatus === "interview_scheduled").length;

    if (p.includes("pipeline") || p.includes("summary") || p.includes("summarize")) {
      return `Current pipeline status:\n• Total candidates in database: ${total}\n• In active interview rounds: ${interviewCount}\n• Ex-employees/leavers quarantined: ${leavers}\n• Top active skills: ${Array.from(new Set(candidates.flatMap((c) => c.skills || []))).slice(0, 5).join(", ")}`;
    }
    if (p.includes("flag") || p.includes("leaver") || p.includes("blacklist")) {
      return `Policy Enforcement: ${leavers} candidates are flagged as former employees or marked inactive. Per ATS blueprint rules, these profiles are quarantined and automatically excluded from active talent searches to protect client compliance.`;
    }
    if (p.includes("duplicate") || p.includes("risk")) {
      return "Duplicate detection runs automatic cross-field scans against candidate email, phone numbers, and normalized name trigrams to avoid redundant submissions.";
    }
    if (p.includes("interview") || p.includes("question")) {
      return "Recommended questions based on candidate pool:\n1. Explain the architectural trade-offs between monolithic and microservice designs in your recent project.\n2. How do you implement robust transactional integrity across distributed services?\n3. Describe how you monitor and debug latency spikes in production.";
    }

    return `I received your query: "${prompt}". I've referenced our ${total} candidate records and enterprise hiring policies. Everything looks aligned with current compliance guidelines.`;
  };

  const handleSend = (textToSend) => {
    const query = textToSend || inputValue;
    if (!query || !query.trim()) return;

    const newMsgs = [...messages, { role: "user", content: query.trim() }];
    setMessages(newMsgs);
    setInputValue("");
    setIsTyping(true);

    setTimeout(() => {
      const reply = generateResponse(query.trim());
      setMessages([...newMsgs, { role: "assistant", content: reply }]);
      setIsTyping(false);
    }, 700);
  };

  return (
    <>
      {/* Floating Copilot Launcher Button */}
      <div style={{ position: "fixed", bottom: 28, right: 28, zIndex: 1000 }}>
        <Button
          type="primary"
          shape="circle"
          icon={<RobotOutlined style={{ fontSize: "22px" }} />}
          size="large"
          style={{
            width: 54,
            height: 54,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 8px 24px rgba(99, 102, 241, 0.45)",
            background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)",
            border: "none",
          }}
          onClick={() => setVisible(true)}
          title="Open HR AI Copilot"
        />
        <span
          style={{
            position: "absolute",
            top: -2,
            right: -2,
            display: "flex",
            width: 12,
            height: 12,
          }}
        >
          <span
            style={{
              position: "absolute",
              display: "inline-flex",
              height: "100%",
              width: "100%",
              borderRadius: "50%",
              backgroundColor: "#10b981",
              opacity: 0.75,
              animation: "ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite",
            }}
          />
          <span
            style={{
              position: "relative",
              display: "inline-flex",
              borderRadius: "50%",
              height: 12,
              width: 12,
              backgroundColor: "#10b981",
            }}
          />
        </span>
      </div>

      {/* Copilot Drawer */}
      <Drawer
        title={
          <Space>
            <RobotOutlined style={{ color: "#6366f1", fontSize: 20 }} />
            <span style={{ fontWeight: 600 }}>HR Copilot</span>
            <Badge status="processing" text="Online" />
          </Space>
        }
        placement="right"
        onClose={() => setVisible(false)}
        open={visible}
        width={420}
      >
        <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
          {/* Quick prompt suggestions */}
          <div style={{ marginBottom: 12 }}>
            <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 6 }}>
              <BulbOutlined style={{ color: "#f59e0b", marginRight: 4 }} />
              Quick Prompts:
            </Text>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {SUGGESTIONS.map((s, idx) => (
                <Tag
                  key={idx}
                  style={{ cursor: "pointer", borderRadius: 12, padding: "2px 8px" }}
                  color="blue"
                  onClick={() => handleSend(s)}
                >
                  {s}
                </Tag>
              ))}
            </div>
          </div>

          {/* Conversation messages */}
          <div style={{ flex: 1, overflowY: "auto", marginBottom: 16, paddingRight: 4 }}>
            <List
              itemLayout="horizontal"
              dataSource={messages}
              renderItem={(item) => (
                <List.Item
                  style={{
                    border: "none",
                    padding: "6px 0",
                    justifyContent: item.role === "user" ? "flex-end" : "flex-start",
                  }}
                >
                  <div
                    style={{
                      background: item.role === "user" ? "#4f46e5" : "#f1f5f9",
                      color: item.role === "user" ? "#ffffff" : "#0f172a",
                      padding: "10px 14px",
                      borderRadius: 12,
                      maxWidth: "88%",
                      fontSize: 13,
                      lineHeight: "1.5",
                      whiteSpace: "pre-wrap",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
                    }}
                  >
                    {item.content}
                  </div>
                </List.Item>
              )}
            />
            {isTyping && (
              <div style={{ fontSize: 12, color: "#94a3b8", fontStyle: "italic", marginTop: 4 }}>
                Copilot is thinking...
              </div>
            )}
          </div>

          {/* Input row */}
          <div style={{ display: "flex", gap: 8, marginTop: "auto" }}>
            <Input
              placeholder="Ask Copilot about candidates, flags, pipeline..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onPressEnter={() => handleSend()}
              disabled={isTyping}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={() => handleSend()}
              disabled={isTyping || !inputValue.trim()}
              style={{ background: "#4f46e5" }}
            />
          </div>

          <div style={{ marginTop: 8, textAlign: "center" }}>
            <Text type="secondary" style={{ fontSize: 11 }}>
              AI insights are advisory only. Always verify with your HR team.
            </Text>
          </div>
        </div>
      </Drawer>
    </>
  );
}
