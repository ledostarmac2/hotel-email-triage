package com.intelligentassistant.emailassistant.repository;

import com.intelligentassistant.emailassistant.model.EmailEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

/**
 * Repository for email entities
 */
@Repository
public interface EmailRepository extends JpaRepository<EmailEntity, String> {
    
    /**
     * Find email by Microsoft Graph email ID
     */
    Optional<EmailEntity> findByEmailId(String emailId);
    
    /**
     * Find emails by user ID
     */
    List<EmailEntity> findByUserIdOrderByReceivedTimeDesc(String userId);
    
    /**
     * Find pending emails for processing
     */
    @Query("SELECT e FROM EmailEntity e WHERE e.processingStatus = 'PENDING' ORDER BY e.receivedTime ASC")
    List<EmailEntity> findPendingEmails();
    
    /**
     * Find emails requiring attention that haven't been notified via WhatsApp
     */
    @Query("SELECT e FROM EmailEntity e WHERE e.requiresAttention = true AND e.whatsappSent = false AND e.userId = :userId")
    List<EmailEntity> findEmailsRequiringWhatsAppNotification(@Param("userId") String userId);
    
    /**
     * Find emails that can be auto-responded
     */
    @Query("SELECT e FROM EmailEntity e WHERE e.requiresAttention = false AND e.autoResponseSent = false AND e.userId = :userId")
    List<EmailEntity> findEmailsForAutoResponse(@Param("userId") String userId);
    
    /**
     * Find emails by category
     */
    List<EmailEntity> findByUserIdAndCategoryOrderByReceivedTimeDesc(String userId, String category);
    
    /**
     * Find emails by sentiment
     */
    List<EmailEntity> findByUserIdAndSentimentOrderByReceivedTimeDesc(String userId, String sentiment);
    
    /**
     * Find emails received after a specific time
     */
    List<EmailEntity> findByUserIdAndReceivedTimeAfterOrderByReceivedTimeDesc(String userId, LocalDateTime after);
    
    /**
     * Count emails by processing status for a user
     */
    @Query("SELECT COUNT(e) FROM EmailEntity e WHERE e.userId = :userId AND e.processingStatus = :status")
    long countByUserIdAndProcessingStatus(@Param("userId") String userId, @Param("status") EmailEntity.ProcessingStatus status);
    
    /**
     * Count emails requiring attention for a user
     */
    @Query("SELECT COUNT(e) FROM EmailEntity e WHERE e.userId = :userId AND e.requiresAttention = true")
    long countEmailsRequiringAttention(@Param("userId") String userId);
    
    /**
     * Find recent emails for historical analysis
     */
    @Query("SELECT e FROM EmailEntity e WHERE e.senderEmail = :senderEmail AND e.userId = :userId ORDER BY e.receivedTime DESC LIMIT 5")
    List<EmailEntity> findRecentEmailsFromSender(@Param("userId") String userId, @Param("senderEmail") String senderEmail);
}
