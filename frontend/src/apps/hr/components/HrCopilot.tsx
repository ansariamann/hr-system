import { useState } from "react";
import { Drawer, Input, List, Typography, Button, Badge, Space } from "antd";
import { RobotOutlined, SendOutlined } from "@ant-design/icons";

const { Text } = Typography;

interface Message {
    role: "user" | "assistant";
    content: string;
}

export const HrCopilot = () => {
    const [visible, setVisible] = useState(false);
    const [messages, setMessages] = useState<Message[]>([
        { role: "assistant", content: "Hello! I am your HR AI Assistant. I can explain candidate flags, summarize resumes, or provide insights. I cannot modify data." }
    ]);
    const [inputValue, setInputValue] = useState("");

    const handleSend = () => {
        if (!inputValue.trim()) return;

        const newMsgs = [...messages, { role: "user", content: inputValue } as Message];
        setMessages(newMsgs);
        setInputValue("");

        // Mock API call
        setTimeout(() => {
            setMessages([...newMsgs, {
                role: "assistant",
                content: "This is a simulated AI response. In production, this would call the /api/copilot endpoint with context from the current view."
            }]);
        }, 1000);
    };

    return (
        <>
            <Button
                type="primary"
                shape="circle"
                icon={<RobotOutlined />}
                size="large"
                style={{ position: 'fixed', bottom: 30, right: 30, zIndex: 1000 }}
                onClick={() => setVisible(true)}
            />

            <Drawer
                title={
                    <Space>
                        <RobotOutlined />
                        HR Copilot <Badge status="processing" text="Online" />
                    </Space>
                }
                placement="right"
                onClose={() => setVisible(false)}
                open={visible}
                width={400}
            >
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <div style={{ flex: 1, overflowY: 'auto', marginBottom: 16 }}>
                        <List
                            itemLayout="horizontal"
                            dataSource={messages}
                            renderItem={(item) => (
                                <List.Item style={{ justifyContent: item.role === 'user' ? 'flex-end' : 'flex-start' }}>
                                    <div style={{
                                        background: item.role === 'user' ? '#1677ff' : '#f0f0f0',
                                        color: item.role === 'user' ? '#fff' : '#000',
                                        padding: '8px 12px',
                                        borderRadius: 8,
                                        maxWidth: '80%'
                                    }}>
                                        <Text style={{ color: 'inherit' }}>{item.content}</Text>
                                    </div>
                                </List.Item>
                            )}
                        />
                    </div>

                    <div style={{ display: 'flex', gap: 8 }}>
                        <Input
                            placeholder="Ask about this candidate..."
                            value={inputValue}
                            onChange={e => setInputValue(e.target.value)}
                            onPressEnter={handleSend}
                        />
                        <Button type="primary" icon={<SendOutlined />} onClick={handleSend} />
                    </div>
                    <div style={{ marginTop: 8, textAlign: 'center' }}>
                        <Text type="secondary" style={{ fontSize: 10 }}>AI insights are advisory only.</Text>
                    </div>
                </div>
            </Drawer>
        </>
    );
};

