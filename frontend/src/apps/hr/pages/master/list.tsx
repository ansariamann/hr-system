import { List, useTable, DateField, TagField, ShowButton } from "@refinedev/antd";
import { Table, Space, Avatar, Typography, Input, InputNumber, Row, Col, Form } from "antd";
import { Search } from "lucide-react";

const { Text } = Typography;
import { ApplicationStatus } from "../../../../shared/types/enums";
import type { Candidate } from "../../../../shared/types/models";

export const MasterDatabaseList = () => {
    const { tableProps, searchFormProps } = useTable<Candidate>({
        resource: "candidates", // Use the candidates resource but present as Master Database
        syncWithLocation: true,
        onSearch: (values: any) => {
            return [
                {
                    field: "name_pattern",
                    operator: "contains",
                    value: values.name_pattern,
                },
                {
                    field: "skills",
                    operator: "contains",
                    value: values.skills,
                },
                {
                    field: "city",
                    operator: "eq",
                    value: values.city,
                },
                {
                    field: "max_experience",
                    operator: "eq",
                    value: values.max_experience,
                }
            ];
        }
    });

    return (
        <List title="Master Database">{/* Search all talent in your pool */}
            <div style={{ marginBottom: 24, background: '#fff', padding: 16, borderRadius: 8 }}>
                <Form {...searchFormProps} layout="vertical">
                    <Row gutter={16}>
                        <Col span={6}>
                            <Form.Item name="name_pattern" label="Name">
                                <Input
                                    placeholder="Search by Name"
                                    prefix={<Search size={16} />}
                                    onPressEnter={() => searchFormProps.form?.submit()}
                                />
                            </Form.Item>
                        </Col>
                        <Col span={6}>
                            <Form.Item name="skills" label="Skills">
                                <Input
                                    placeholder="Python, React..."
                                    prefix={<Search size={16} />}
                                    onPressEnter={() => searchFormProps.form?.submit()}
                                />
                            </Form.Item>
                        </Col>
                        <Col span={6}>
                            <Form.Item name="city" label="City">
                                <Input
                                    placeholder="City / Location"
                                    onPressEnter={() => searchFormProps.form?.submit()}
                                />
                            </Form.Item>
                        </Col>
                        <Col span={6}>
                            <Form.Item name="max_experience" label="Max Experience">
                                <InputNumber
                                    placeholder="Years"
                                    style={{ width: '100%' }}
                                    min={0}
                                    onPressEnter={() => searchFormProps.form?.submit()}
                                />
                            </Form.Item>
                        </Col>
                    </Row>
                </Form>
            </div>

            <Table {...tableProps} rowKey="id">
                <Table.Column
                    title="Candidate"
                    dataIndex="name"
                    render={(_, record: Candidate) => (
                        <Space>
                            <Avatar size="large" style={{ backgroundColor: '#1890ff' }}>
                                {record.name?.charAt(0).toUpperCase()}
                            </Avatar>
                            <Space direction="vertical" size={0}>
                                <Text strong>{record.name}</Text>
                                <Text type="secondary" style={{ fontSize: 12 }}>{record.email}</Text>
                            </Space>
                        </Space>
                    )}
                />

                <Table.Column
                    title="Skills"
                    dataIndex="skills"
                    render={(value) => {
                        if (!value || !value.skills) return <Text type="secondary">-</Text>;
                        return (
                            <Space wrap>
                                {Array.isArray(value.skills) && value.skills.slice(0, 3).map((skill: string) => (
                                    <TagField key={skill} value={skill} />
                                ))}
                                {Array.isArray(value.skills) && value.skills.length > 3 && (
                                    <TagField value={`+${value.skills.length - 3}`} />
                                )}
                            </Space>
                        );
                    }}
                />

                <Table.Column
                    dataIndex="status"
                    title="Status"
                    render={(value) => (
                        <TagField value={value} color={
                            value === ApplicationStatus.HIRED ? "green" :
                                value === ApplicationStatus.REJECTED ? "red" :
                                    "blue"
                        } />
                    )}
                />

                <Table.Column
                    title="Location"
                    dataIndex="location"
                    render={(value) => <Text>{value || '-'}</Text>}
                />

                <Table.Column
                    title="Experience"
                    dataIndex="experience"
                    render={(value) => {
                        if (!value) return <Text type="secondary">-</Text>;
                        return <Text>{value.years ? `${value.years} Years` : 'Unknown'}</Text>;
                    }}
                />

                <Table.Column
                    dataIndex="created_at"
                    title="Added On"
                    render={(value) => <DateField value={value} format="MMM DD, YYYY" />}
                />

                <Table.Column
                    title="Actions"
                    dataIndex="actions"
                    render={(_, record: any) => (
                        <Space>
                            <ShowButton hideText size="small" recordItemId={record.id} resource="candidates" />
                        </Space>
                    )}
                />
            </Table>
        </List>
    );
};
