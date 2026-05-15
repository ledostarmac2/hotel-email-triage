package com.intelligentassistant.emailassistant.controller;

import com.intelligentassistant.emailassistant.model.EmailEntity;
import com.intelligentassistant.emailassistant.repository.EmailRepository;
import com.intelligentassistant.emailassistant.service.AutoResponseService;
import com.intelligentassistant.emailassistant.service.EmailAnalysisService;
import com.intelligentassistant.emailassistant.service.ScheduledEmailProcessor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

/**
 * REST controller for email management
 */
@RestController
@RequestMapping("/emails")
@CrossOrigin(origins = "*")
public class EmailController {
    
    private final EmailRepository emailRepository;
    private final EmailAnalysisService emailAnalysisService;
    private final AutoResponseService autoResponseService;
    private final ScheduledEmailProcessor scheduledEmailProcessor;
    
    public EmailController(EmailRepository emailRepository,
                          EmailAnalysisService emailAnalysisService,
                          AutoResponseService autoResponseService,
                          ScheduledEmailProcessor scheduledEmailProcessor) {
        this.emailRepository = emailRepository;
        this.emailAnalysisService = emailAnalysisService;
        this.autoResponseService = autoResponseService;
        this.scheduledEmailProcessor = scheduledEmailProcessor;
    }
    
    /**
     * Get all emails for a user
     */
    @GetMapping("/user/{userId}")
    public ResponseEntity<List<EmailEntity>> getUserEmails(@PathVariable String userId,
                                                          @RequestParam(defaultValue = "0") int page,
                                                          @RequestParam(defaultValue = "20") int size) {
        try {
            List<EmailEntity> emails = emailRepository.findByUserIdOrderByReceivedTimeDesc(userId);
            
            // Simple pagination
            int start = page * size;
            int end = Math.min(start + size, emails.size());
            
            if (start < emails.size()) {
                List<EmailEntity> paginatedEmails = emails.subList(start, end);
                return ResponseEntity.ok(paginatedEmails);
            } else {
                return ResponseEntity.ok(List.of());
            }
        } catch (Exception e) {
            return ResponseEntity.internalServerError().build();
        }
    }
    
    /**
     * Get emails requiring attention
     */
    @GetMapping("/user/{userId}/requiring-attention")
    public ResponseEntity<List<EmailEntity>> getEmailsRequiringAttention(@PathVariable String userId) {
        try {
            List<EmailEntity> emails = emailRepository.findEmailsRequiringWhatsAppNotification(userId);
            return ResponseEntity.ok(emails);
        } catch (Exception e) {
            return ResponseEntity.internalServerError().build();
        }
    }
    
    /**
     * Get emails by category
     */
    @GetMapping("/user/{userId}/category/{category}")
    public ResponseEntity<List<EmailEntity>> getEmailsByCategory(@PathVariable String userId,
                                                                @PathVariable String category) {
        try {
            List<EmailEntity> emails = emailRepository.findByUserIdAndCategoryOrderByReceivedTimeDesc(userId, category);
            return ResponseEntity.ok(emails);
        } catch (Exception e) {
            return ResponseEntity.internalServerError().build();
        }
    }
    
    /**
     * Get emails by sentiment
     */
    @GetMapping("/user/{userId}/sentiment/{sentiment}")
    public ResponseEntity<List<EmailEntity>> getEmailsBySentiment(@PathVariable String userId,
                                                                 @PathVariable String sentiment) {
        try {
            List<EmailEntity> emails = emailRepository.findByUserIdAndSentimentOrderByReceivedTimeDesc(userId, sentiment);
            return ResponseEntity.ok(emails);
        } catch (Exception e) {
            return ResponseEntity.internalServerError().build();
        }
    }
    
    /**
     * Get specific email by ID
     */
    @GetMapping("/{emailId}")
    public ResponseEntity<EmailEntity> getEmail(@PathVariable String emailId) {
        try {
            Optional<EmailEntity> email = emailRepository.findByEmailId(emailId);
            return email.map(ResponseEntity::ok)
                       .orElse(ResponseEntity.notFound().build());
        } catch (Exception e) {
            return ResponseEntity.internalServerError().build();
        }
    }
    
    /**
     * Get email statistics for a user
     */
    @GetMapping("/user/{userId}/stats")
    public ResponseEntity<EmailAnalysisService.EmailStats> getEmailStats(@PathVariable String userId) {
        try {
            EmailAnalysisService.EmailStats stats = emailAnalysisService.getEmailStats(userId);
            return ResponseEntity.ok(stats);
        } catch (Exception e) {
            return ResponseEntity.internalServerError().build();
        }
    }
    
    /**
     * Get auto-response statistics
     */
    @GetMapping("/user/{userId}/auto-response-stats")
    public ResponseEntity<AutoResponseService.AutoResponseStats> getAutoResponseStats(@PathVariable String userId) {
        try {
            AutoResponseService.AutoResponseStats stats = autoResponseService.getAutoResponseStats(userId);
            return ResponseEntity.ok(stats);
        } catch (Exception e) {
            return ResponseEntity.internalServerError().build();
        }
    }
    
    /**
     * Generate response preview for an email
     */
    @PostMapping("/{emailId}/preview-response")
    public ResponseEntity<String> previewResponse(@PathVariable String emailId,
                                                 @RequestParam String userId) {
        try {
            Optional<EmailEntity> emailOpt = emailRepository.findByEmailId(emailId);
            if (emailOpt.isEmpty()) {
                return ResponseEntity.notFound().build();
            }
            
            String preview = autoResponseService.generateResponsePreview(emailOpt.get(), userId).block();
            return ResponseEntity.ok(preview);
        } catch (Exception e) {
            return ResponseEntity.internalServerError().build();
        }
    }
    
    /**
     * Send auto-response for a specific email
     */
    @PostMapping("/{emailId}/send-response")
    public ResponseEntity<Boolean> sendAutoResponse(@PathVariable String emailId,
                                                   @RequestParam String userId) {
        try {
            Optional<EmailEntity> emailOpt = emailRepository.findByEmailId(emailId);
            if (emailOpt.isEmpty()) {
                return ResponseEntity.notFound().build();
            }
            
            Boolean success = autoResponseService.generateAndSendResponse(emailOpt.get(), userId).block();
            return ResponseEntity.ok(success);
        } catch (Exception e) {
            return ResponseEntity.internalServerError().build();
        }
    }
    
    /**
     * Trigger manual email processing
     */
    @PostMapping("/trigger-processing")
    public ResponseEntity<String> triggerProcessing() {
        try {
            scheduledEmailProcessor.triggerEmailProcessing();
            return ResponseEntity.ok("Email processing triggered successfully");
        } catch (Exception e) {
            return ResponseEntity.internalServerError().body("Failed to trigger processing: " + e.getMessage());
        }
    }
    
    /**
     * Trigger manual auto-response processing
     */
    @PostMapping("/trigger-auto-responses")
    public ResponseEntity<String> triggerAutoResponses() {
        try {
            scheduledEmailProcessor.triggerAutoResponseProcessing();
            return ResponseEntity.ok("Auto-response processing triggered successfully");
        } catch (Exception e) {
            return ResponseEntity.internalServerError().body("Failed to trigger auto-responses: " + e.getMessage());
        }
    }
    
    /**
     * Get processing statistics
     */
    @GetMapping("/processing-stats")
    public ResponseEntity<ScheduledEmailProcessor.ProcessingStats> getProcessingStats() {
        try {
            ScheduledEmailProcessor.ProcessingStats stats = scheduledEmailProcessor.getProcessingStats();
            return ResponseEntity.ok(stats);
        } catch (Exception e) {
            return ResponseEntity.internalServerError().build();
        }
    }
    
    /**
     * Get recent emails (last 24 hours)
     */
    @GetMapping("/user/{userId}/recent")
    public ResponseEntity<List<EmailEntity>> getRecentEmails(@PathVariable String userId,
                                                            @RequestParam(defaultValue = "24") int hours) {
        try {
            LocalDateTime since = LocalDateTime.now().minusHours(hours);
            List<EmailEntity> emails = emailRepository.findByUserIdAndReceivedTimeAfterOrderByReceivedTimeDesc(userId, since);
            return ResponseEntity.ok(emails);
        } catch (Exception e) {
            return ResponseEntity.internalServerError().build();
        }
    }
}
