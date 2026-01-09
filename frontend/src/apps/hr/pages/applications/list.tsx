import { List, useTable, DateField, TagField } from "@refinedev/antd";
import { Table, Space } from "antd";
import { ApplicationStatus } from "../../../shared/types/enums";

export const ApplicationList = () => {
    const { tableProps } = useTable({
        syncWithLocation: true,
    });

    return (
        <List>
            <Table {...tableProps} rowKey="id">
                <Table.Column dataIndex="id" title="ID" />
                <Table.Column
                    dataIndex={["candidate", "name"]}
                    title="Candidate"
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
                    render={(value) => <DateField value={value} />}
                />
            </Table>
        </List>
    );
};
