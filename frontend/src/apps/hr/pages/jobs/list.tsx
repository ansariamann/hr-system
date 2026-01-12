import { List, useTable, TagField } from "@refinedev/antd";
import { Table, Space, Typography } from "antd";
import type { Job } from "../../../../shared/types/models";

const { Text } = Typography;

export const JobList = () => {
    const { tableProps } = useTable<Job>({
        syncWithLocation: true,
    });

    return (
        <List>
            <Table {...tableProps} rowKey="id">
                <Table.Column
                    dataIndex="title"
                    title="Job Title"
                    render={(value) => <Text strong>{value}</Text>}
                />
                <Table.Column
                    dataIndex="department"
                    title="Department"
                />
                <Table.Column
                    dataIndex="location"
                    title="Location"
                />
                <Table.Column
                    dataIndex="is_active"
                    title="Status"
                    render={(value) => (
                        <TagField value={value ? "Active" : "Closed"} color={value ? "green" : "default"} />
                    )}
                />
                <Table.Column
                    title="Actions"
                    dataIndex="actions"
                    render={() => (
                        <Space>
                            {/* Actions placeholder */}
                        </Space>
                    )}
                />
            </Table>
        </List>
    );
};
