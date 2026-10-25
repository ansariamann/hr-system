package com.ats.worker;

import com.ats.domain.entity.ResumeJob;
import com.ats.domain.repository.CandidateRepository;
import com.ats.domain.repository.ResumeJobRepository;
import com.ats.resume.PdfExtractionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.jobrunr.jobs.annotations.Job;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.File;
import java.time.Instant;
import java.util.UUID;

/**
 * JobRunr background worker for async resume processing.
 * Replaces Python Celery resume_tasks.py.
 *
 * Jobs are strongly-typed Java lambdas; JobRunr serializes them
 * to a PostgreSQL or Redis storage backend with a built-in dashboard.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ResumeProcessingWorker {

    private final PdfExtractionService pdfExtractionService;
    private final ResumeJobRepository resumeJobRepository;
    private final CandidateRepository candidateRepository;

    /**
     * Process a single resume job — called by JobRunr scheduler.
     */
    @Job(name = "Resume Processing: %0", retries = 3)
    @Transactional
    public void processResume(UUID resumeJobId) {
        ResumeJob job = resumeJobRepository.findById(resumeJobId)
                .orElseThrow(() -> new RuntimeException("ResumeJob not found: " + resumeJobId));

        log.info("Processing resume job: {} file: {}", resumeJobId, job.getFileName());

        try {
            job.setStatus("PROCESSING");
            resumeJobRepository.save(job);

            File pdfFile = new File(job.getFilePath());
            if (!pdfFile.exists()) {
                throw new RuntimeException("PDF file not found: " + job.getFilePath());
            }

            String extractedText = pdfExtractionService.extractText(pdfFile);

            // Update candidate with extracted text as key_skill (simplified — expand for production)
            if (job.getClientId() != null) {
                log.info("Extracted {} chars from resume for job {}", extractedText.length(), resumeJobId);
                // In production: parse structured data (name, email, phone, skills)
                // and create/update Candidate entity
            }

            job.setStatus("COMPLETED");
            job.setProcessedAt(Instant.now());
            resumeJobRepository.save(job);

            log.info("Resume job {} completed successfully", resumeJobId);

        } catch (Exception e) {
            log.error("Resume job {} failed: {}", resumeJobId, e.getMessage(), e);
            job.setStatus("FAILED");
            job.setErrorMessage(e.getMessage());
            resumeJobRepository.save(job);
            throw new RuntimeException("Resume processing failed", e);
        }
    }
}
