import { useShow } from "@refinedev/core";
import type { IResourceComponentsProps } from "@refinedev/core";
import {
    Show,
    TextField,
    DateField,
    TagField,
    NumberField,
    EmailField
} from "@refinedev/antd";
import { Typography, Row, Col, Tag, Descriptions, Divider } from "antd";
import type { Candidate } from "../../../../shared/types/models";
import { CandidateStatus as CandidateStatusEnum } from "../../../../shared/types/enums";

const { Title, Text } = Typography;

export const CandidateShow: React.FC<IResourceComponentsProps> = () => {
    const { queryResult } = useShow<Candidate>();
    const { data, isLoading } = queryResult;

    const record = data?.data;

    const getSkillsList = (skillsData: any): string[] => {
        if (!skillsData) return [];
        if (Array.isArray(skillsData)) return skillsData;
        if (typeof skillsData === 'object' && Array.isArray(skillsData.skills)) return skillsData.skills;
        return [];
    };

    const skills = getSkillsList(record?.skills);

    return (
        <Show isLoading={isLoading}>
            <Title level={4}>Candidate Details</Title>

            <Row gutter={[16, 16]}>
                <Col span={24}>
                    <Descriptions bordered column={{ xs: 1, sm: 2, md: 3 }} layout="vertical">
                        <Descriptions.Item label="Name">{record?.name}</Descriptions.Item>
                        <Descriptions.Item label="Email">
                            <EmailField value={record?.email} />
                        </Descriptions.Item>
                        <Descriptions.Item label="Phone">
                            <TextField value={record?.phone} />
                        </Descriptions.Item>
                        <Descriptions.Item label="Status">
                            <TagField
                                value={record?.status}
                                color={
                                    record?.status === CandidateStatusEnum.HIRED ? "green" :
                                        record?.status === CandidateStatusEnum.REJECTED ? "red" :
                                            record?.status === CandidateStatusEnum.ACTIVE ? "blue" : "default"
                                }
                            />
                        </Descriptions.Item>
                        <Descriptions.Item label="Current CTC">
                            <NumberField value={record?.ctc_current ?? 0} options={{ style: 'currency', currency: 'USD' }} />
                        </Descriptions.Item>
                        <Descriptions.Item label="Expected CTC">
                            <NumberField value={record?.ctc_expected ?? 0} options={{ style: 'currency', currency: 'USD' }} />
                        </Descriptions.Item>
                        <Descriptions.Item label="Created At">
                            <DateField value={record?.created_at} />
                        </Descriptions.Item>
                    </Descriptions>
                </Col>
            </Row>

            <Divider orientation="left">Skills & Experience</Divider>

            <Row gutter={[16, 16]}>
                <Col span={24}>
                    <Title level={5}>Skills</Title>
                    <div style={{ marginBottom: 24 }}>
                        {skills.length > 0 ? (
                            skills.map((skill, index) => (
                                <Tag key={index} color="geekblue">{skill}</Tag>
                            ))
                        ) : (
                            <Text type="secondary">No specific skills listed</Text>
                        )}
                    </div>
                </Col>

                <Col span={24}>
                    <Title level={5}>Experience Info</Title>
                    {record?.experience ? (
                        <div style={{ backgroundColor: '#f5f5f5', padding: '12px', borderRadius: '6px' }}>
                            <pre style={{ whiteSpace: 'pre-wrap' }}>
                                {JSON.stringify(record.experience, null, 2)}
                            </pre>
                        </div>
                    ) : (
                        <Text type="secondary">No experience data</Text>
                    )}
                </Col>
            </Row>

        </Show>
    );
};
