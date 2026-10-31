package com.ats.resume;

import com.ats.domain.entity.Candidate;
import com.ats.domain.entity.ResumeJob;
import com.ats.domain.enums.CandidateStatus;
import com.ats.domain.repository.ResumeJobRepository;
import com.ats.service.CandidateService;
import lombok.Builder;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.File;
import java.io.IOException;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.time.Instant;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Service to parse resumes (PDF / TXT), extract structured candidate info,
 * and save Candidate records to database.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ResumeParserService {

    private final PdfExtractionService pdfExtractionService;
    private final CandidateService candidateService;
    private final ResumeJobRepository resumeJobRepository;

    private static final Pattern EMAIL_PATTERN = Pattern.compile(
            "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,6}");

    private static final Pattern PHONE_PATTERN = Pattern.compile(
            "(\\+?\\d{1,3}[-.\\s]?)?\\(?\\d{3}\\)?[-.\\s]?\\d{3}[-.\\s]?\\d{4}");

    private static final Pattern EXP_PATTERN = Pattern.compile(
            "(\\d+)\\+?\\s*(?:years?|yrs?)(?:\\s+of)?(?:\\s+experience)?", Pattern.CASE_INSENSITIVE);

    private static final List<String> KNOWN_SKILLS = List.of(
            "Java", "Spring Boot", "Spring", "React", "Node.js", "Python", "FastAPI", "Django",
            "PostgreSQL", "MySQL", "MongoDB", "Redis", "Kafka", "Docker", "Kubernetes",
            "AWS", "Azure", "GCP", "TypeScript", "JavaScript", "HTML", "CSS", "Git",
            "CI/CD", "Linux", "Microservices", "REST API", "GraphQL", "Hibernate", "JPA"
    );

    private static final List<String> KNOWN_CITIES = List.of(
            "Bangalore", "Bengaluru", "Hyderabad", "Pune", "Mumbai", "Delhi", "Noida",
            "Gurgaon", "Chennai", "London", "San Francisco", "New York", "Remote"
    );

    @Data
    @Builder
    public static class ParsedResumeData {
        private String name;
        private String email;
        private String phone;
        private String location;
        private List<String> skills;
        private Integer experienceYears;
        private String summary;
        private String rawText;
        private String fileName;
    }

    /**
     * Parse a resume file and ingest candidate into database.
     */
    @Transactional
    public Candidate parseAndIngest(File file, String originalFileName, UUID clientId, UUID userId) throws IOException {
        String rawText = extractRawText(file, originalFileName);
        ParsedResumeData parsed = parseText(rawText, originalFileName);

        // Build Candidate entity
        Candidate candidate = Candidate.builder()
                .clientId(clientId)
                .name(parsed.getName())
                .email(parsed.getEmail())
                .phone(parsed.getPhone())
                .location(parsed.getLocation() != null ? parsed.getLocation() : "Remote")
                .skills(parsed.getSkills())
                .keySkill(parsed.getSkills().isEmpty() ? "General" : parsed.getSkills().get(0))
                .totalExperienceYears(parsed.getExperienceYears() != null ? new BigDecimal(parsed.getExperienceYears()) : BigDecimal.ZERO)
                .status(CandidateStatus.ACTIVE)
                .source("RESUME_UPLOAD")
                .remark("Ingested via resume upload: " + originalFileName)
                .otherDetails(Map.of(
                        "parsed_summary", parsed.getSummary() != null ? parsed.getSummary() : "",
                        "raw_text_snippet", rawText.length() > 500 ? rawText.substring(0, 500) + "..." : rawText,
                        "file_name", originalFileName
                ))
                .build();

        Candidate saved = candidateService.create(candidate, userId);

        // Track resume job
        ResumeJob resumeJob = ResumeJob.builder()
                .clientId(clientId)
                .fileName(originalFileName)
                .filePath(file.getAbsolutePath())
                .status("COMPLETED")
                .processedAt(Instant.now())
                .build();
        resumeJobRepository.save(resumeJob);

        log.info("Successfully ingested candidate {} from file {}", saved.getName(), originalFileName);
        return saved;
    }

    public String extractRawText(File file, String fileName) throws IOException {
        if (fileName != null && fileName.toLowerCase().endsWith(".pdf")) {
            return pdfExtractionService.extractText(file);
        } else {
            return Files.readString(file.toPath());
        }
    }

    public ParsedResumeData parseText(String text, String fileName) {
        String cleanText = text != null ? text.trim() : "";

        // Extract Email
        String email = null;
        Matcher emailMatcher = EMAIL_PATTERN.matcher(cleanText);
        if (emailMatcher.find()) {
            email = emailMatcher.group().toLowerCase();
        }

        // Extract Phone
        String phone = null;
        Matcher phoneMatcher = PHONE_PATTERN.matcher(cleanText);
        if (phoneMatcher.find()) {
            phone = phoneMatcher.group().trim();
        }

        // Extract Experience
        Integer experienceYears = null;
        Matcher expMatcher = EXP_PATTERN.matcher(cleanText);
        if (expMatcher.find()) {
            try {
                experienceYears = Integer.parseInt(expMatcher.group(1));
            } catch (NumberFormatException ignored) {}
        }

        // Extract Location
        String location = "Remote";
        for (String city : KNOWN_CITIES) {
            if (Pattern.compile("\\b" + Pattern.quote(city) + "\\b", Pattern.CASE_INSENSITIVE).matcher(cleanText).find()) {
                location = city;
                break;
            }
        }

        // Extract Skills
        List<String> matchedSkills = new ArrayList<>();
        for (String skill : KNOWN_SKILLS) {
            if (Pattern.compile("\\b" + Pattern.quote(skill) + "\\b", Pattern.CASE_INSENSITIVE).matcher(cleanText).find()) {
                matchedSkills.add(skill);
            }
        }

        // Extract Name from first line or fileName
        String name = null;
        String[] lines = cleanText.split("\r?\n");
        for (String line : lines) {
            String trimmed = line.trim();
            if (trimmed.length() >= 3 && trimmed.length() <= 50 && !trimmed.contains("@") && !trimmed.matches(".*\\d{5,}.*")) {
                if (!trimmed.equalsIgnoreCase("resume") && !trimmed.equalsIgnoreCase("curriculum vitae") && !trimmed.equalsIgnoreCase("cv")) {
                    name = trimmed;
                    break;
                }
            }
        }
        if (name == null || name.isBlank()) {
            name = fileName != null ? fileName.replaceFirst("[.][^.]+$", "").replace("_", " ") : "Candidate Profile";
        }

        return ParsedResumeData.builder()
                .name(name)
                .email(email != null ? email : "candidate_" + System.currentTimeMillis() + "@talent.local")
                .phone(phone)
                .location(location)
                .skills(matchedSkills)
                .experienceYears(experienceYears != null ? experienceYears : 3)
                .summary(cleanText.length() > 250 ? cleanText.substring(0, 250) + "..." : cleanText)
                .rawText(cleanText)
                .fileName(fileName)
                .build();
    }
}

