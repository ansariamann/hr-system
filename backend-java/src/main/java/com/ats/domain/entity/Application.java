package com.ats.domain.entity;

import com.ats.domain.enums.ApplicationStatus;
import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import jakarta.persistence.*;
import lombok.*;

import java.time.Instant;
import java.util.UUID;

/**
 * Application entity linking Candidates to Jobs with an FSM-managed status.
 * Maps to the 'applications' PostgreSQL table (RLS-protected by client_id).
 */
@Entity
@Table(name = "applications",
        indexes = {
                @Index(name = "idx_applications_client_id", columnList = "client_id"),
                @Index(name = "idx_applications_candidate_id", columnList = "candidate_id"),
                @Index(name = "idx_applications_deleted_at", columnList = "deleted_at")
        })
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Application extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "client_id", nullable = false)
    private UUID clientId;

    @JsonIgnore
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "client_id", insertable = false, updatable = false)
    private Client client;

    @Column(name = "candidate_id", nullable = false)
    private UUID candidateId;

    @JsonIgnore
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "candidate_id", insertable = false, updatable = false)
    private Candidate candidate;

    @Column(name = "job_id")
    private UUID jobId;

    @JsonIgnore
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "job_id", insertable = false, updatable = false)
    private Job job;

    @Column(name = "job_title", length = 255)
    private String jobTitle;

    @Column(name = "application_date", nullable = false)
    @Builder.Default
    private Instant applicationDate = Instant.now();

    @Column(name = "source", nullable = false, length = 100)
    @Builder.Default
    private String source = "MANUAL";

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 50)
    @Builder.Default
    private ApplicationStatus status = ApplicationStatus.RECEIVED;

    @Column(name = "status_updated_at", nullable = false)
    @Builder.Default
    private Instant statusUpdatedAt = Instant.now();

    @Column(name = "flagged_for_review", nullable = false)
    @Builder.Default
    private Boolean flaggedForReview = false;

    @Column(name = "flag_reason", columnDefinition = "TEXT")
    private String flagReason;

    @Column(name = "notes", columnDefinition = "TEXT")
    private String notes;

    @Column(name = "applied_by_user_id")
    private UUID appliedByUserId;

    @JsonIgnore
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "applied_by_user_id", insertable = false, updatable = false)
    private User appliedByUser;

    @Column(name = "hr_interview_acknowledged", nullable = false)
    @Builder.Default
    private Boolean hrInterviewAcknowledged = false;

    @Column(name = "hr_interview_acknowledged_at")
    private Instant hrInterviewAcknowledgedAt;

    @Column(name = "hr_interview_acknowledged_by")
    private UUID hrInterviewAcknowledgedBy;

    @Column(name = "hr_interview_ack_note", columnDefinition = "TEXT")
    private String hrInterviewAckNote;

    @Column(name = "deleted_at")
    private Instant deletedAt;

    // ─── Helpers ────────────────────────────────────────────────────────
    public boolean isDeleted() {
        return deletedAt != null;
    }

    public void softDelete() {
        this.deletedAt = Instant.now();
    }
}
