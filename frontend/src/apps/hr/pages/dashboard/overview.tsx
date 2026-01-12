import { Row, Col, Typography, Card, List, Avatar, Space } from "antd";
import {
    Users,
    FileText,
    CheckCircle,
    Briefcase,
    TrendingUp,
    Clock
} from "lucide-react";
import { StatsCard } from "../../../../shared/components/ui/StatsCard";

const { Title, Text } = Typography;

export const DashboardOverview = () => {
    // Mock Data
    const stats = [
        {
            title: "Total Candidates",
            value: "1,234",
            icon: Users,
            trend: { value: 12, isPositive: true },
            description: "vs last month"
        },
        {
            title: "Active Applications",
            value: "45",
            icon: FileText,
            trend: { value: 5, isPositive: true },
            description: "currently processing"
        },
        {
            title: "Hired this Month",
            value: "8",
            icon: CheckCircle,
            trend: { value: 2, isPositive: false },
            description: "vs target of 10"
        },
        {
            title: "Open Positions",
            value: "12",
            icon: Briefcase,
            description: "across 3 departments"
        }
    ];

    const activities = [
        {
            user: "Sarah Smith",
            action: "moved candidate",
            target: "John Doe",
            status: "Interview",
            time: "2 hours ago"
        },
        {
            user: "Mike Johnson",
            action: "hired",
            target: "Emily Brown",
            status: "Hired",
            time: "4 hours ago"
        },
        {
            user: "System",
            action: "received application",
            target: "Alex Wilson",
            status: "New",
            time: "5 hours ago"
        },
        {
            user: "Sarah Smith",
            action: "scheduled interview",
            target: "Chris Davis",
            status: "Interview",
            time: "1 day ago"
        }
    ];

    return (
        <div style={{ padding: "24px" }}>
            <div style={{ marginBottom: "24px" }}>
                <Title level={2}>Dashboard</Title>
                <Text type="secondary">Overview of your recruitment pipeline</Text>
            </div>

            <Row gutter={[16, 16]}>
                {stats.map((stat, index) => (
                    <Col xs={24} sm={12} lg={6} key={index}>
                        <StatsCard {...stat} />
                    </Col>
                ))}
            </Row>

            <Row gutter={[16, 16]} style={{ marginTop: "24px" }}>
                <Col xs={24} lg={16}>
                    <Card title={<Space><TrendingUp size={18} /> Recruitment Activity</Space>}>
                        <div style={{ height: "300px", display: "flex", alignItems: "center", justifyContent: "center", color: "#999" }}>
                            Chart Placeholder (Recharts Integration)
                        </div>
                    </Card>
                </Col>
                <Col xs={24} lg={8}>
                    <Card title={<Space><Clock size={18} /> Recent Activity</Space>}>
                        <List
                            itemLayout="horizontal"
                            dataSource={activities}
                            renderItem={(item) => (
                                <List.Item>
                                    <List.Item.Meta
                                        avatar={<Avatar style={{ backgroundColor: '#1890ff' }}>{item.user[0]}</Avatar>}
                                        title={
                                            <Space size={4}>
                                                <Text strong>{item.user}</Text>
                                                <Text type="secondary">{item.action}</Text>
                                                <Text strong>{item.target}</Text>
                                            </Space>
                                        }
                                        description={item.time}
                                    />
                                </List.Item>
                            )}
                        />
                    </Card>
                </Col>
            </Row>
        </div>
    );
};
