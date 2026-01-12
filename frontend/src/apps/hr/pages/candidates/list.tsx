import { List, useTable, DateField, TagField, ShowButton } from "@refinedev/antd";
import { Table, Space, Avatar, Typography } from "antd";

const { Text } = Typography;
import { ApplicationStatus } from "../../../../shared/types/enums";
import type { Candidate } from "../../../../shared/types/models";

export const CandidateList = () => {
    const { tableProps } = useTable<Candidate>({
        syncWithLocation: true,
    });

    return (
        <List>
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
