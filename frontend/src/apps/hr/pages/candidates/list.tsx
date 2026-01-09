import { List, useTable, DateField, TagField, ShowButton } from "@refinedev/antd";
import { Table, Space } from "antd";
import { ApplicationStatus } from "../../../shared/types/enums";
// import { Candidate } from "../../../shared/types/models";

export const CandidateList = () => {
    const { tableProps } = useTable({
        syncWithLocation: true,
    });

    return (
        <List>
            <Table {...tableProps} rowKey="id">
                <Table.Column dataIndex="id" title="ID" />
                <Table.Column dataIndex="name" title="Name" />
                <Table.Column dataIndex="email" title="Email" />
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
                    render={(value) => <DateField value={value} />}
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
