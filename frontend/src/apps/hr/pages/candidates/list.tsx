import { List, useTable, DateField, TagField, ShowButton } from "@refinedev/antd";
import { Table, Space, Avatar, Typography, Input, Form } from "antd";
import { Search } from "lucide-react";

const { Text } = Typography;
import { ApplicationStatus } from "../../../../shared/types/enums";
import type { Candidate } from "../../../../shared/types/models";

export const CandidateList = () => {
    const { tableProps, searchFormProps } = useTable<Candidate>({
        syncWithLocation: true,
        onSearch: (values: any) => {
            return [
                {
                    field: "name_pattern",
                    operator: "eq",
                    value: values.name_pattern,
                },
                {
                    field: "skills",
                    operator: "eq",
                    value: values.skills,
                }
            ];
        }
    });

    return (
        <List>
            <div style={{ marginBottom: 24, background: '#fff', padding: 16, borderRadius: 8 }}>
                <Form {...searchFormProps} layout="inline">
                    <Form.Item name="name_pattern">
                        <Input
                            placeholder="Search by Name..."
                            prefix={<Search size={16} />}
                            style={{ width: 300 }}
                        />
                    </Form.Item>
                    <Form.Item name="skills">
                        <Input
                            placeholder="Search by Skills (e.g. Python, React)..."
                            prefix={<Search size={16} />}
                            style={{ width: 300 }}
                        />
                    </Form.Item>
                    <Form.Item>
                        <ShowButton hideText icon={<Search size={16} />} onClick={() => searchFormProps.form?.submit()} />
                    </Form.Item>
                </Form>
            </div>
            <Table {...tableProps} rowKey="id">
                <Table.Column
                    title="Candidate"
                    dataIndex="name"
                    render={(_, record: Candidate) => (
                        <Space>
                            <Avatar>{record.name?.charAt(0).toUpperCase()}</Avatar>
                            <Space direction="vertical" size={0}>
                                <Text strong>{record.name}</Text>
                                <Text type="secondary" style={{ fontSize: 12 }}>{record.email}</Text>
                            </Space>
                        </Space>
                    )}
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
                    dataIndex="created_at"
                    title="Applied At"
                    render={(value) => <DateField value={value} format="MMM DD, YYYY" />}
                />
                <Table.Column
                    title="Actions"
                    dataIndex="actions"
                    render={(_, record: any) => (
                        <Space>
                            <ShowButton hideText size="small" recordItemId={record.id} />
                        </Space>
                    )}
                />
            </Table>
        </List>
    );
};
