import { List, useTable, DateField, TagField } from "@refinedev/antd";
import { Table, Space, Avatar, Typography } from "antd";
import { ApplicationStatus } from "../../../../shared/types/enums";
import type { Application } from "../../../../shared/types/models";

const { Text } = Typography;

export const ApplicationList = () => {
    const { tableProps } = useTable<Application>({
        syncWithLocation: true,
    });

    return (
        <List>
            <Table {...tableProps} rowKey="id">
                <Table.Column
                    title="Candidate"
                    dataIndex={["candidate", "name"]}
                    render={(_, record: Application) => (
                        <Space>
                            <Avatar>{record.candidate?.name?.charAt(0).toUpperCase()}</Avatar>
                            <Space direction="vertical" size={0}>
                                <Text strong>{record.candidate?.name}</Text>
                                <Text type="secondary" style={{ fontSize: 12 }}>{record.candidate?.email}</Text>
                            </Space>
                        </Space>
                    )}
                />
                <Table.Column
                    title="Role"
                    dataIndex={["job", "title"]}
                    render={(_, record: Application) => record.job?.title || "General Application"}
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
            </Table>
        </List>
    );
};
