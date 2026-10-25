package com.ats.service;

import com.ats.domain.entity.Candidate;
import com.ats.domain.repository.CandidateRepository;
import com.ats.exception.ResourceNotFoundException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.text.similarity.LevenshteinDistance;
import org.apache.commons.text.similarity.JaroWinklerSimilarity;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;

/**
 * Duplicate candidate detection service.
 *
 * Ports duplicate_detection_service.py: uses Levenshtein distance and
 * Jaro-Winkler similarity from Apache commons-text to detect near-duplicate
 * candidates by name, email, and phone.
 *
 * Thresholds match the Python implementation:
 *   - Email exact match → definite duplicate
 *   - Phone exact match → definite duplicate
 *   - Name similarity > 0.85 (Jaro-Winkler) AND phone fuzzy match → likely duplicate
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DuplicateDetectionService {

    private final CandidateRepository candidateRepository;

    private final LevenshteinDistance levenshtein = LevenshteinDistance.getDefaultInstance();
    private final JaroWinklerSimilarity jaroWinkler = new JaroWinklerSimilarity();

    private static final double NAME_SIMILARITY_THRESHOLD = 0.85;
    private static final int PHONE_EDIT_DISTANCE_THRESHOLD = 2;

    /**
     * Find potential duplicate candidates for a given candidate profile.
     * Returns a list of (candidate, score, reason) tuples.
     */
    @Transactional(readOnly = true)
    public List<DuplicateMatch> findDuplicates(UUID clientId, String name, String email, String phone) {
        List<DuplicateMatch> matches = new ArrayList<>();

        // First: exact email/phone lookup
        List<Candidate> exactMatches = candidateRepository.findPotentialDuplicates(clientId, email, phone);
        for (Candidate c : exactMatches) {
            String reason = determineDuplicateReason(c, email, phone);
            matches.add(new DuplicateMatch(c, 1.0, reason));
        }

        // Second: fuzzy name+phone check for candidates not already found
        Set<UUID> alreadyFound = new HashSet<>();
        exactMatches.forEach(c -> alreadyFound.add(c.getId()));

        if (name != null && !name.isBlank()) {
            candidateRepository.findAllByClientId(clientId, org.springframework.data.domain.Pageable.unpaged())
                    .stream()
                    .filter(c -> !alreadyFound.contains(c.getId()))
                    .forEach(c -> {
                        double nameSim = computeNameSimilarity(name, c.getName());
                        if (nameSim >= NAME_SIMILARITY_THRESHOLD) {
                            boolean phoneClose = phone != null && c.getPhone() != null &&
                                    levenshtein.apply(normalizePhone(phone), normalizePhone(c.getPhone())) <= PHONE_EDIT_DISTANCE_THRESHOLD;
                            if (phoneClose) {
                                matches.add(new DuplicateMatch(c, nameSim, "Similar name and phone"));
                                alreadyFound.add(c.getId());
                            }
                        }
                    });
        }

        matches.sort(Comparator.comparingDouble(DuplicateMatch::score).reversed());
        return matches;
    }

    private double computeNameSimilarity(String a, String b) {
        if (a == null || b == null) return 0.0;
        return jaroWinkler.apply(a.toLowerCase().trim(), b.toLowerCase().trim());
    }

    private String normalizePhone(String phone) {
        return phone == null ? "" : phone.replaceAll("[^0-9]", "");
    }

    private String determineDuplicateReason(Candidate c, String email, String phone) {
        if (email != null && email.equalsIgnoreCase(c.getEmail())) return "Exact email match";
        if (phone != null && phone.equals(c.getPhone())) return "Exact phone match";
        return "Email or phone match";
    }

    public record DuplicateMatch(Candidate candidate, double score, String reason) {}
}
