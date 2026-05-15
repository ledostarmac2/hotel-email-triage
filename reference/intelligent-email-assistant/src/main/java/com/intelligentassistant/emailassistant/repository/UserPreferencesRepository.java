package com.intelligentassistant.emailassistant.repository;

import com.intelligentassistant.emailassistant.model.UserPreferencesEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

/**
 * Repository for user preferences entities
 */
@Repository
public interface UserPreferencesRepository extends JpaRepository<UserPreferencesEntity, String> {
    
    /**
     * Find user preferences by user ID
     */
    Optional<UserPreferencesEntity> findByUserId(String userId);
    
    /**
     * Check if preferences exist for a user
     */
    boolean existsByUserId(String userId);
}
