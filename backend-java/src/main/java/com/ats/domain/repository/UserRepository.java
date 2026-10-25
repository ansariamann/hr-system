package com.ats.domain.repository;

import com.ats.domain.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface UserRepository extends JpaRepository<User, UUID> {

    Optional<User> findByEmail(String email);

    boolean existsByEmail(String email);

    List<User> findAllByClientId(UUID clientId);

    @Query("SELECT u FROM User u WHERE u.clientId = :clientId AND u.isActive = true")
    List<User> findActiveByClientId(@Param("clientId") UUID clientId);
}
