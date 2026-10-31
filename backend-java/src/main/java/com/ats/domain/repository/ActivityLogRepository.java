package com.ats.domain.repository;

import com.ats.domain.entity.ActivityLog;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface ActivityLogRepository extends JpaRepository<ActivityLog, UUID> {

    Page<ActivityLog> findAllByClientIdOrderByCreatedAtDesc(UUID clientId, Pageable pageable);

    /** Tenant-scoped entity lookup — always filter by clientId to prevent cross-tenant access. */
    List<ActivityLog> findByClientIdAndEntityIdOrderByCreatedAtDesc(UUID clientId, UUID entityId);

    List<ActivityLog> findByClientIdAndActionTypeOrderByCreatedAtDesc(UUID clientId, String actionType);
}
