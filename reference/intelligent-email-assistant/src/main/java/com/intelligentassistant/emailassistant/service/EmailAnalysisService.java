package com.intelligentassistant.emailassistant.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.intelligentassistant.emailassistant.model.*;
import com.intelligentassistant.emailassistant.repository.EmailRepository;
import com.intelligentassistant.emailassistant.repository.UserPreferencesRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * Core service for analyzing emails using LLM providers
 */
@Service
public class EmailAnalysisService {
    
    private static final Logger logger = LoggerFactory.getLogger(EmailAnalysisService.class);
    
    private final LLMService llmService;
    private final EmailRepository emailRepository;
    private final UserPreferencesRepository userPreferencesRepository;
    private final WhatsAppService whatsAppService;
    private final ObjectMapper objectMapper;
    
    public EmailAnalysisService(LLMService llmService,
                               EmailRepository emailRepository,
                               UserPreferencesRepository userPreferencesRepository,
                               WhatsAppService whatsAppService,
                               ObjectMapper objectMapper) {
        this.llmService = llmService;
        this.emailRepository = emailRepository;
        this.userPreferencesRepository = userPreferencesRepository;
        this.whatsAppService = whatsAppService;
        this.objectMapper = objectMapper;
    }
    
    /**
     * Process and analyze a single email
     */
    public Mono<EmailEntity> processEmail(EmailAnalysisRequest request, String userId) {
        return Mono.fromCallable(() -> {
            // Check if email already exists
            Optional<EmailEntity> existingEmail = emailRepository.findByEmailId(request.getEmailId());
            if (existingEmail.isPresent()) {
                logger.info("Email already processed: {}", request.getEmailId());
                return existingEmail.get();
            }
            
            // Create new email entity
            EmailEntity emailEntity = new EmailEntity(
                request.getEmailId(), 
                userId, 
                request.getSubject(),
                request.getContent(), 
                request.getSenderEmail(), 
                request.getSenderName(),
                request.getReceivedTime()
            );
            emailEntity.setProcessingStatus(EmailEntity.ProcessingStatus.PROCESSING);
            emailEntity = emailRepository.save(emailEntity);
            
            return emailEntity;
        })
        .flatMap(emailEntity -> {
            // Get user preferences and historical data
            return prepareAnalysisRequest(request, userId)
                    .flatMap(enrichedRequest -> {
                        // Analyze email with LLM
                        return llmService.analyzeEmail(enrichedRequest)
                                .flatMap(response -> {
                                    // Update email entity with analysis results
                                    return updateEmailWithAnalysis(emailEntity, response, enrichedRequest);
                                });
                    });
        })
        .doOnError(error -> {
            logger.error("Error processing email: " + request.getEmailId(), error);
            // Update email status to failed
            emailRepository.findByEmailId(request.getEmailId())
                    .ifPresent(email -> {
                        email.setProcessingStatus(EmailEntity.ProcessingStatus.FAILED);
                        emailRepository.save(email);
                    });
        });
    }
    
    /**
     * Process multiple emails in batch
     */
    public Mono<List<EmailEntity>> processEmailsBatch(List<EmailAnalysisRequest> requests, String userId) {
        logger.info("Processing batch of {} emails for user: {}", requests.size(), userId);
        
        List<Mono<EmailEntity>> emailMonos = requests.stream()
                .map(request -> processEmail(request, userId)
                        .onErrorResume(error -> {
                            logger.error("Failed to process email in batch: " + request.getEmailId(), error);
                            return Mono.empty();
                        }))
                .toList();
        
        return Mono.when(emailMonos)
                .then(Mono.fromCallable(() -> {
                    // Collect results
                    List<EmailEntity> results = new ArrayList<>();
                    emailMonos.forEach(mono -> {
                        try {
                            EmailEntity result = mono.block();
                            if (result != null) {
                                results.add(result);
                            }
                        } catch (Exception e) {
                            logger.warn("Error collecting batch result", e);
                        }
                    });
                    return results;
                }));
    }
    
    /**
     * Send WhatsApp notifications for emails requiring attention
     */
    public Mono<Void> sendNotifications(String userId) {
        return Mono.fromCallable(() -> {
            // Get user preferences
            Optional<UserPreferencesEntity> prefsOpt = userPreferencesRepository.findByUserId(userId);
            if (prefsOpt.isEmpty() || !Boolean.TRUE.equals(prefsOpt.get().getEnableWhatsAppNotifications())) {
                logger.info("WhatsApp notifications disabled for user: {}", userId);
                return null;
            }
            
            UserPreferencesEntity prefs = prefsOpt.get();
            String whatsappNumber = prefs.getWhatsAppNumber();
            
            if (whatsappNumber == null || whatsappNumber.trim().isEmpty()) {
                logger.warn("No WhatsApp number configured for user: {}", userId);
                return null;
            }
            
            // Get emails requiring WhatsApp notification
            List<EmailEntity> emailsToNotify = emailRepository.findEmailsRequiringWhatsAppNotification(userId);
            
            for (EmailEntity email : emailsToNotify) {
                try {
                    boolean sent = whatsAppService.sendEmailNotification(
                        whatsappNumber,
                        email.getSenderName(),
                        email.getSubject(),
                        "This email requires your personal attention based on AI analysis."
                    );
                    
                    if (sent) {
                        email.setWhatsappSent(true);
                        emailRepository.save(email);
                        logger.info("WhatsApp notification sent for email: {}", email.getEmailId());
                    }
                } catch (Exception e) {
                    logger.error("Failed to send WhatsApp notification for email: " + email.getEmailId(), e);
                }
            }
            
            return null;
        }).then();
    }
    
    private Mono<EmailAnalysisRequest> prepareAnalysisRequest(EmailAnalysisRequest request, String userId) {
        return Mono.fromCallable(() -> {
            // Get user preferences
            Optional<UserPreferencesEntity> prefsOpt = userPreferencesRepository.findByUserId(userId);
            if (prefsOpt.isPresent()) {
                UserPreferencesEntity prefsEntity = prefsOpt.get();
                UserPreferences prefs = convertToUserPreferences(prefsEntity);
                request.setUserPreferences(prefs);
            }
            
            // Get historical responses from the same sender
            if (request.getSenderEmail() != null) {
                List<EmailEntity> historicalEmails = emailRepository.findRecentEmailsFromSender(userId, request.getSenderEmail());
                List<String> historicalResponses = historicalEmails.stream()
                        .filter(email -> email.getAutoResponseSent() != null && email.getAutoResponseSent())
                        .map(email -> "Previous response style example") // In real implementation, store actual responses
                        .toList();
                request.setHistoricalResponses(historicalResponses);
            }
            
            return request;
        });
    }
    
    private Mono<EmailEntity> updateEmailWithAnalysis(EmailEntity emailEntity, EmailAnalysisResponse response, EmailAnalysisRequest request) {
        return Mono.fromCallable(() -> {
            // Update email entity with analysis results
            emailEntity.setRequiresAttention(response.isRequiresPersonalAttention());
            emailEntity.setConfidenceScore(response.getConfidenceScore());
            emailEntity.setCategory(response.getCategory());
            emailEntity.setSentiment(response.getSentiment());
            emailEntity.setProcessedTime(LocalDateTime.now());
            emailEntity.setProcessingStatus(EmailEntity.ProcessingStatus.COMPLETED);
            
            // Set LLM provider used
            if (request.getUserPreferences() != null && request.getUserPreferences().getUserId() != null) {
                Optional<UserPreferencesEntity> prefsOpt = userPreferencesRepository.findByUserId(request.getUserPreferences().getUserId());
                prefsOpt.ifPresent(prefs -> emailEntity.setLlmProvider(prefs.getDefaultLlmProvider()));
            }
            
            return emailRepository.save(emailEntity);
        });
    }
    
    private UserPreferences convertToUserPreferences(UserPreferencesEntity entity) {
        UserPreferences prefs = new UserPreferences();
        prefs.setUserId(entity.getUserId());
        prefs.setResponseStyle(entity.getResponseStyle());
        prefs.setEnableWhatsAppNotifications(entity.getEnableWhatsAppNotifications());
        prefs.setWhatsAppNumber(entity.getWhatsAppNumber());
        prefs.setResponseDelayMinutes(entity.getResponseDelayMinutes());
        prefs.setTimezone(entity.getTimezone());
        
        // Convert JSON arrays back to lists
        try {
            if (entity.getKeywordsRequiringAttention() != null) {
                List<String> keywords = objectMapper.readValue(
                    entity.getKeywordsRequiringAttention(), 
                    new TypeReference<List<String>>() {}
                );
                prefs.setKeywordsRequiringAttention(keywords);
            }
            
            if (entity.getTrustedSenders() != null) {
                List<String> trusted = objectMapper.readValue(
                    entity.getTrustedSenders(), 
                    new TypeReference<List<String>>() {}
                );
                prefs.setTrustedSenders(trusted);
            }
            
            if (entity.getAutoRespondSenders() != null) {
                List<String> autoRespond = objectMapper.readValue(
                    entity.getAutoRespondSenders(), 
                    new TypeReference<List<String>>() {}
                );
                prefs.setAutoRespondSenders(autoRespond);
            }
            
            if (entity.getWorkingHours() != null) {
                List<String> hours = objectMapper.readValue(
                    entity.getWorkingHours(), 
                    new TypeReference<List<String>>() {}
                );
                prefs.setWorkingHours(hours);
            }
        } catch (Exception e) {
            logger.error("Error converting user preferences JSON", e);
        }
        
        return prefs;
    }
    
    /**
     * Get email statistics for a user
     */
    public EmailStats getEmailStats(String userId) {
        long totalEmails = emailRepository.countByUserIdAndProcessingStatus(userId, EmailEntity.ProcessingStatus.COMPLETED);
        long requiresAttention = emailRepository.countEmailsRequiringAttention(userId);
        long pendingProcessing = emailRepository.countByUserIdAndProcessingStatus(userId, EmailEntity.ProcessingStatus.PENDING);
        
        EmailStats stats = new EmailStats();
        stats.setTotalProcessed(totalEmails);
        stats.setRequiringAttention(requiresAttention);
        stats.setPendingProcessing(pendingProcessing);
        stats.setAutoResponded(totalEmails - requiresAttention);
        
        return stats;
    }
    
    // Inner class for email statistics
    public static class EmailStats {
        private long totalProcessed;
        private long requiringAttention;
        private long pendingProcessing;
        private long autoResponded;
        
        // Getters and setters
        public long getTotalProcessed() { return totalProcessed; }
        public void setTotalProcessed(long totalProcessed) { this.totalProcessed = totalProcessed; }
        
        public long getRequiringAttention() { return requiringAttention; }
        public void setRequiringAttention(long requiringAttention) { this.requiringAttention = requiringAttention; }
        
        public long getPendingProcessing() { return pendingProcessing; }
        public void setPendingProcessing(long pendingProcessing) { this.pendingProcessing = pendingProcessing; }
        
        public long getAutoResponded() { return autoResponded; }
        public void setAutoResponded(long autoResponded) { this.autoResponded = autoResponded; }
    }
}
