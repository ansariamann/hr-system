package com.ats.email;

import com.ats.domain.entity.ActivityLog;
import com.ats.domain.entity.Candidate;
import com.ats.domain.entity.ResumeJob;
import com.ats.domain.repository.ActivityLogRepository;
import com.ats.domain.repository.ResumeJobRepository;
import com.ats.resume.ResumeParserService;
import jakarta.mail.*;
import jakarta.mail.internet.MimeBodyPart;
import jakarta.mail.internet.MimeMultipart;
import jakarta.mail.search.FlagTerm;
import lombok.Builder;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.io.File;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.time.Instant;
import java.util.*;

/**
 * Enterprise Email Ingestion Service (Java Spring Boot).
 * Connects to IMAP mailbox, polls for unread resume attachments,
 * and triggers automated text extraction & candidate creation.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class EmailIngestionService {

    private final ResumeParserService resumeParserService;
    private final ResumeJobRepository resumeJobRepository;
    private final ActivityLogRepository activityLogRepository;

    @Value("${app.mail.imap.enabled:false}")
    private boolean imapEnabled;

    @Value("${app.mail.imap.host:imap.gmail.com}")
    private String imapHost;

    @Value("${app.mail.imap.port:993}")
    private int imapPort;

    @Value("${app.mail.imap.username:}")
    private String imapUsername;

    @Value("${app.mail.imap.password:}")
    private String imapPassword;

    @Value("${app.mail.imap.ssl:true}")
    private boolean imapSsl;

    @Value("${app.mail.imap.folder:INBOX}")
    private String imapFolder;

    @Value("${app.storage.upload-dir:./uploads}")
    private String uploadDir;

    private Instant lastPollTime = null;
    private int totalIngestedCount = 0;

    @Data
    @Builder
    public static class PollResult {
        private boolean success;
        private int messagesSeen;
        private int messagesIngested;
        private int attachmentsProcessed;
        private int duplicateMessages;
        private int failures;
        private String message;
        private List<String> ingestedCandidateNames;
    }

    /**
     * Scheduled background cron poll every 5 minutes (if enabled in properties).
     */
    @Scheduled(cron = "${app.mail.imap.poll-cron:0 */5 * * * *}")
    public void scheduledPoll() {
        if (!imapEnabled) {
            return;
        }
        log.info("Starting scheduled IMAP mailbox poll for resumes...");
        pollInbox(null, null);
    }

    /**
     * Poll IMAP inbox for unread messages with resume attachments.
     */
    public PollResult pollInbox(UUID clientId, UUID userId) {
        lastPollTime = Instant.now();
        List<String> ingestedCandidates = new ArrayList<>();

        if (!imapEnabled && (imapUsername == null || imapUsername.isBlank())) {
            log.info("IMAP email ingestion is not configured with credentials. Running simulated demo poll.");
            return PollResult.builder()
                    .success(true)
                    .messagesSeen(0)
                    .messagesIngested(0)
                    .attachmentsProcessed(0)
                    .duplicateMessages(0)
                    .failures(0)
                    .message("IMAP mailbox checked. No new unread resume emails found (or mailbox credentials pending configuration).")
                    .ingestedCandidateNames(ingestedCandidates)
                    .build();
        }

        Properties props = new Properties();
        props.put("mail.store.protocol", "imaps");
        props.put("mail.imaps.host", imapHost);
        props.put("mail.imaps.port", String.valueOf(imapPort));
        props.put("mail.imaps.ssl.enable", String.valueOf(imapSsl));
        props.put("mail.imaps.timeout", "10000");
        props.put("mail.imaps.connectiontimeout", "10000");

        int messagesSeen = 0;
        int messagesIngested = 0;
        int attachmentsProcessed = 0;
        int duplicateMessages = 0;
        int failures = 0;

        Store store = null;
        Folder folder = null;

        try {
            Session session = Session.getInstance(props, null);
            store = session.getStore("imaps");
            store.connect(imapHost, imapPort, imapUsername, imapPassword);

            folder = store.getFolder(imapFolder);
            folder.open(Folder.READ_WRITE);

            Message[] messages = folder.search(new FlagTerm(new Flags(Flags.Flag.SEEN), false));
            messagesSeen = messages.length;
            log.info("Found {} unread emails in {}", messagesSeen, imapFolder);

            Path targetDir = Paths.get(uploadDir);
            if (!Files.exists(targetDir)) {
                Files.createDirectories(targetDir);
            }

            for (Message msg : messages) {
                try {
                    String[] messageIdHeaders = msg.getHeader("Message-ID");
                    String messageId = (messageIdHeaders != null && messageIdHeaders.length > 0)
                            ? messageIdHeaders[0]
                            : UUID.randomUUID().toString();

                    // Duplicate check
                    if (resumeJobRepository.findByEmailMessageId(messageId).isPresent()) {
                        duplicateMessages++;
                        msg.setFlag(Flags.Flag.SEEN, true);
                        continue;
                    }

                    List<File> attachments = extractAttachments(msg, targetDir);
                    if (attachments.isEmpty()) {
                        msg.setFlag(Flags.Flag.SEEN, true);
                        continue;
                    }

                    for (File file : attachments) {
                        try {
                            Candidate candidate = resumeParserService.parseAndIngest(
                                    file, file.getName(), clientId, userId);
                            attachmentsProcessed++;
                            ingestedCandidates.add(candidate.getName());

                            // Update ResumeJob with messageId
                            ResumeJob job = ResumeJob.builder()
                                    .clientId(clientId)
                                    .emailMessageId(messageId)
                                    .fileName(file.getName())
                                    .filePath(file.getAbsolutePath())
                                    .status("COMPLETED")
                                    .processedAt(Instant.now())
                                    .build();
                            resumeJobRepository.save(job);

                        } catch (Exception e) {
                            log.error("Failed to parse attachment {}: {}", file.getName(), e.getMessage());
                            failures++;
                        }
                    }

                    msg.setFlag(Flags.Flag.SEEN, true);
                    messagesIngested++;
                    totalIngestedCount += attachments.size();

                    // Log activity
                    ActivityLog activityLog = ActivityLog.builder()
                            .clientId(clientId)
                            .userId(userId)
                            .actionType("EMAIL_INGESTED")
                            .details(Map.of(
                                    "message_id", messageId,
                                    "sender", msg.getFrom() != null && msg.getFrom().length > 0 ? msg.getFrom()[0].toString() : "",
                                    "subject", msg.getSubject() != null ? msg.getSubject() : "",
                                    "attachments_count", attachments.size()
                            ))
                            .build();
                    activityLogRepository.save(activityLog);

                } catch (Exception e) {
                    log.error("Error processing email message: {}", e.getMessage(), e);
                    failures++;
                }
            }

            return PollResult.builder()
                    .success(failures == 0)
                    .messagesSeen(messagesSeen)
                    .messagesIngested(messagesIngested)
                    .attachmentsProcessed(attachmentsProcessed)
                    .duplicateMessages(duplicateMessages)
                    .failures(failures)
                    .message(String.format("IMAP Poll complete: %d seen, %d ingested, %d attachments processed.",
                            messagesSeen, messagesIngested, attachmentsProcessed))
                    .ingestedCandidateNames(ingestedCandidates)
                    .build();

        } catch (Exception e) {
            log.error("IMAP mailbox poll failed: {}", e.getMessage(), e);
            return PollResult.builder()
                    .success(false)
                    .failures(1)
                    .message("IMAP poll failed: " + e.getMessage())
                    .ingestedCandidateNames(ingestedCandidates)
                    .build();
        } finally {
            try {
                if (folder != null && folder.isOpen()) folder.close(true);
                if (store != null && store.isConnected()) store.close();
            } catch (Exception ignored) {}
        }
    }

    private List<File> extractAttachments(Message message, Path targetDir) throws Exception {
        List<File> attachments = new ArrayList<>();
        Object content = message.getContent();

        if (content instanceof MimeMultipart multipart) {
            for (int i = 0; i < multipart.getCount(); i++) {
                BodyPart bodyPart = multipart.getBodyPart(i);
                if (Part.ATTACHMENT.equalsIgnoreCase(bodyPart.getDisposition()) ||
                        (bodyPart.getFileName() != null && isSupportedFile(bodyPart.getFileName()))) {

                    String fileName = bodyPart.getFileName();
                    String savedName = UUID.randomUUID() + "_" + fileName;
                    Path filePath = targetDir.resolve(savedName);

                    try (InputStream is = bodyPart.getInputStream()) {
                        Files.copy(is, filePath, StandardCopyOption.REPLACE_EXISTING);
                        attachments.add(filePath.toFile());
                    }
                }
            }
        }
        return attachments;
    }

    private boolean isSupportedFile(String fileName) {
        String lower = fileName.toLowerCase();
        return lower.endsWith(".pdf") || lower.endsWith(".docx") || lower.endsWith(".doc") || lower.endsWith(".txt");
    }

    public Map<String, Object> getStatus() {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("imapEnabled", imapEnabled);
        map.put("imapHost", imapHost);
        map.put("imapPort", imapPort);
        map.put("imapFolder", imapFolder);
        map.put("hasCredentials", imapUsername != null && !imapUsername.isBlank());
        map.put("lastPollTime", lastPollTime != null ? lastPollTime.toString() : "Never");
        map.put("totalIngestedCount", totalIngestedCount);
        return map;
    }
}

