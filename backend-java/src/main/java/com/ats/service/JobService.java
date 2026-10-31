package com.ats.service;

import com.ats.domain.entity.Job;
import com.ats.domain.repository.JobRepository;
import com.ats.exception.ResourceNotFoundException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class JobService {

    private final JobRepository jobRepository;

    @Transactional(readOnly = true)
    public Page<Job> listJobs(UUID clientId, Pageable pageable) {
        if (clientId == null) {
            return jobRepository.findAll(pageable);
        }
        return jobRepository.findAllByClientId(clientId, pageable);
    }

    @Transactional(readOnly = true)
    public Job getById(UUID id, UUID clientId) {
        if (clientId == null) {
            return jobRepository.findById(id)
                    .orElseThrow(() -> new ResourceNotFoundException("Job", id));
        }
        return jobRepository.findByIdAndClientId(id, clientId)
                .orElseThrow(() -> new ResourceNotFoundException("Job", id));
    }

    @Transactional(readOnly = true)
    public List<Job> getVacantOpenJobs(UUID clientId) {
        if (clientId == null) {
            return jobRepository.findVacantOpenJobs();
        }
        return jobRepository.findVacantOpenJobsByClient(clientId);
    }

    @Transactional
    public Job create(Job job) {
        Job saved = jobRepository.save(job);
        log.info("Job created: {} for client {}", saved.getId(), saved.getClientId());
        return saved;
    }

    @Transactional
    public Job update(UUID id, UUID clientId, Job updates) {
        Job existing = getById(id, clientId);

        if (updates.getTitle() != null)          existing.setTitle(updates.getTitle());
        if (updates.getCompanyName() != null)    existing.setCompanyName(updates.getCompanyName());
        if (updates.getRequirements() != null)   existing.setRequirements(updates.getRequirements());
        if (updates.getDepartment() != null)     existing.setDepartment(updates.getDepartment());
        if (updates.getLocation() != null)       existing.setLocation(updates.getLocation());
        if (updates.getStatus() != null)         existing.setStatus(updates.getStatus());
        if (updates.getOpeningsCount() != null)  existing.setOpeningsCount(updates.getOpeningsCount());
        if (updates.getVacant() != null)         existing.setVacant(updates.getVacant());
        if (updates.getSalaryLpa() != null)      existing.setSalaryLpa(updates.getSalaryLpa());
        if (updates.getClosingDate() != null)    existing.setClosingDate(updates.getClosingDate());
        if (updates.getEmploymentType() != null) existing.setEmploymentType(updates.getEmploymentType());

        return jobRepository.save(existing);
    }

    @Transactional
    public void delete(UUID id, UUID clientId) {
        Job job = getById(id, clientId);
        jobRepository.delete(job);
        log.info("Job deleted: {}", id);
    }
}
