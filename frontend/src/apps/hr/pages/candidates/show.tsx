import { Show, TextField, DateField, MarkdownField } from "@refinedev/antd";
import { Typography } from "antd";

const { Title } = Typography;

export const CandidateShow = () => {
    return (
        <Show isLoading={false}>
            <Title level={5}>Candidate Details</Title>
            <TextField value="Candidate Name Placeholder" />

            <Title level={5}>Status</Title>
            <TextField value="SCREENING" />

            <Title level={5}>Resume</Title>
            <MarkdownField value="**Resume content placeholder**" />
        </Show>
    );
};
