package com.intelligentassistant.emailassistant.service;

import com.intelligentassistant.emailassistant.model.EmailAnalysisRequest;
import com.intelligentassistant.emailassistant.model.EmailEntity;
import com.intelligentassistant.emailassistant.model.UserPreferencesEntity;
import com.intelligentassistant.emailassistant.repository.EmailRepository;
import com.intelligentassistant.emailassistant.repository.UserPreferencesRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.TimeUnit;

/**
 * Service for automatically responding to emails that don't require personal attention
 */
@Service
public class AutoResponseService {
    
    private static final Logger logger = LoggerFactory.getLogger(AutoResponseService.class);
    
    @Value("${app.email.max-response-length}")
    private int maxResponseLength;
    
    private final LLMService llmService;
    private final MicrosoftGraphService microsoftGraphService;
    private final EmailRepository emailRepository;
    private final UserPreferencesRepository userPreferencesRepository;
    private final EmailAnalysisService emailAnalysisService;
    
    public AutoResponseService(LLMService llmService,
                              MicrosoftGraphService microsoftGraphService,
                              EmailRepository emailRepository,
                              UserPreferencesRepository userPreferencesRepository,
                              EmailAnalysisService emailAnalysisService) {
        this.llmService = llmService;
        this.microsoftGraphService = microsoftGraphService;
        this.emailRepository = emailRepository;
        this.userPreferencesRepository = userPreferencesRepository;
        this.emailAnalysisService = emailAnalysisService;
    }
    
    /**
     * Process auto-responses for a specific user
     */
    public Mono<Integer> processAutoResponses(String userId) {
        return Mono.fromCallable(() -> {
            logger.info("Processing auto-responses for user: {}", userId);
            
            // Get user preferences
            Optional<UserPreferencesEntity> prefsOpt = userPreferencesRepository.findByUserId(userId);
            if (prefsOpt.isEmpty()) {
                logger.info("No preferences found for user: {}", userId);
                return 0;
            }
            
            UserPreferencesEntity prefs = prefsOpt.get();
            int delayMinutes = prefs.getResponseDelayMinutes() != null ? prefs.getResponseDelayMinutes() : 5;
            
            // Get emails that can be auto-responded and have passed the delay period
            List<EmailEntity> emailsForAutoResponse = emailRepository.findEmailsForAutoResponse(userId);
            
            int responsesGenerated = 0;
            for (EmailEntity email : emailsForAutoResponse) {
                // Check if enough time has passed since the email was received
                if (shouldDelayResponse(email, delayMinutes)) {
                    continue;
                }
                
                try {
                    boolean responseGenerated = generateAndSendResponse(email, userId).block();
                    if (responseGenerated) {
                        responsesGenerated++;
                    }
                } catch (Exception e) {
                    logger.error("Failed to generate auto-response for email: " + email.getEmailId(), e);
                }
            }
            
            logger.info("Generated {} auto-responses for user: {}", responsesGenerated, userId);
            return responsesGenerated;
        });
    }
    
    /**
     * Generate and send an auto-response for a specific email
     */
    public Mono<Boolean> generateAndSendResponse(EmailEntity emailEntity, String userId) {
        return Mono.fromCallable(() -> {
            // Convert EmailEntity back to EmailAnalysisRequest
            EmailAnalysisRequest request = convertToAnalysisRequest(emailEntity);
            return request;
        })
        .flatMap(request -> {
            // Prepare the request with user preferences and historical data
            return prepareAnalysisRequest(request, userId);
        })
        .flatMap(enrichedRequest -> {
            // Generate response using LLM
            return llmService.generateResponse(enrichedRequest);
        })
        .flatMap(generatedResponse -> {
            // Process and validate the response
            return processGeneratedResponse(generatedResponse, emailEntity);
        })
        .flatMap(finalResponse -> {
            // Send the response via Microsoft Graph
            return sendEmailResponse(emailEntity.getEmailId(), finalResponse);
        })
        .flatMap(sent -> {
            // Update email entity to mark as auto-responded
            return updateEmailAsResponded(emailEntity, sent);
        })
        .doOnSuccess(success -> {
            if (success) {
                logger.info("Auto-response sent successfully for email: {}", emailEntity.getEmailId());
            } else {
                logger.warn("Failed to send auto-response for email: {}", emailEntity.getEmailId());
            }
        })
        .doOnError(error -> {
            logger.error("Error in auto-response process for email: " + emailEntity.getEmailId(), error);
        })
        .onErrorReturn(false);
    }
    
    /**
     * Generate response without sending (for preview/testing)
     */
    public Mono<String> generateResponsePreview(EmailEntity emailEntity, String userId) {
        return Mono.fromCallable(() -> {
            EmailAnalysisRequest request = convertToAnalysisRequest(emailEntity);
            return request;
        })
        .flatMap(request -> prepareAnalysisRequest(request, userId))
        .flatMap(enrichedRequest -> llmService.generateResponse(enrichedRequest))
        .map(this::cleanAndValidateResponse);
    }
    
    private boolean shouldDelayResponse(EmailEntity email, int delayMinutes) {
        if (email.getReceivedTime() == null) {
            return false;
        }
        
        LocalDateTime cutoffTime = LocalDateTime.now().minusMinutes(delayMinutes);
        return email.getReceivedTime().isAfter(cutoffTime);
    }
    
    private EmailAnalysisRequest convertToAnalysisRequest(EmailEntity entity) {
        EmailAnalysisRequest request = new EmailAnalysisRequest();
        request.setEmailId(entity.getEmailId());
        request.setSubject(entity.getSubject());
        request.setContent(entity.getContent());
        request.setSenderEmail(entity.getSenderEmail());
        request.setSenderName(entity.getSenderName());
        request.setReceivedTime(entity.getReceivedTime());
        return request;
    }
    
    private Mono<EmailAnalysisRequest> prepareAnalysisRequest(EmailAnalysisRequest request, String userId) {
        return Mono.fromCallable(() -> {
            // Get user preferences and historical data (reuse from EmailAnalysisService)
            Optional<UserPreferencesEntity> prefsOpt = userPreferencesRepository.findByUserId(userId);
            if (prefsOpt.isPresent()) {
                UserPreferencesEntity prefsEntity = prefsOpt.get();
                // Convert to UserPreferences using the method from EmailAnalysisService
                // For now, we'll set basic preferences
                request.setConversationContext("Auto-response generation for email that doesn't require personal attention");
            }
            
            // Get historical responses from the same sender
            if (request.getSenderEmail() != null) {
                List<EmailEntity> historicalEmails = emailRepository.findRecentEmailsFromSender(userId, request.getSenderEmail());
                List<String> historicalResponses = historicalEmails.stream()
                        .filter(email -> email.getAutoResponseSent() != null && email.getAutoResponseSent())
                        .map(email -> "Professional and courteous response pattern")
                        .toList();
                request.setHistoricalResponses(historicalResponses);
            }
            
            return request;
        });
    }
    
    private Mono<String> processGeneratedResponse(String rawResponse, EmailEntity emailEntity) {
        return Mono.fromCallable(() -> {
            String processedResponse = cleanAndValidateResponse(rawResponse);
            
            // Add personalization
            processedResponse = personalizeResponse(processedResponse, emailEntity.getSenderName());
            
            return processedResponse;
        });
    }
    
    private String cleanAndValidateResponse(String response) {
        if (response == null || response.trim().isEmpty()) {
            return getDefaultResponse();
        }
        
        // Clean the response
        String cleaned = response.trim();
        
        // Remove any potential system prompts or unwanted content
        cleaned = cleaned.replaceAll("(?i)^(system:|assistant:|ai:|response:)\\s*", "");
        
        // Ensure the response is not too long
        if (cleaned.length() > maxResponseLength) {
            cleaned = cleaned.substring(0, maxResponseLength - 3) + "...";
        }
        
        // Ensure the response ends properly
        if (!cleaned.endsWith(".") && !cleaned.endsWith("!") && !cleaned.endsWith("?")) {
            cleaned += ".";
        }
        
        return cleaned;
    }
    
    private String personalizeResponse(String response, String senderName) {
        if (senderName != null && !senderName.trim().isEmpty()) {
            // Extract first name if possible
            String firstName = senderName.split(" ")[0];
            
            // Add greeting if response doesn't start with one
            if (!response.toLowerCase().startsWith("hi") && 
                !response.toLowerCase().startsWith("hello") && 
                !response.toLowerCase().startsWith("dear")) {
                response = "Hi " + firstName + ",\n\n" + response;
            }
        }
        
        // Add professional closing if not present
        if (!response.toLowerCase().contains("best regards") && 
            !response.toLowerCase().contains("sincerely") &&
            !response.toLowerCase().contains("thank you")) {
            response += "\n\nBest regards";
        }
        
        return response;
    }
    
    private Mono<Boolean> sendEmailResponse(String emailId, String responseContent) {
        return Mono.fromCallable(() -> {
            try {
                microsoftGraphService.replyToEmail(emailId, responseContent);
                return true;
            } catch (Exception e) {
                logger.error("Failed to send email response for: " + emailId, e);
                return false;
            }
        });
    }
    
    private Mono<Boolean> updateEmailAsResponded(EmailEntity emailEntity, boolean responseSent) {
        return Mono.fromCallable(() -> {
            emailEntity.setAutoResponseSent(responseSent);
            if (responseSent) {
                emailEntity.setUpdatedAt(LocalDateTime.now());
            }
            emailRepository.save(emailEntity);
            return responseSent;
        });
    }
    
    private String getDefaultResponse() {
        return "Thank you for your email. I have received your message and will get back to you as soon as possible.";
    }
    
    /**
     * Get statistics about auto-responses
     */
    public AutoResponseStats getAutoResponseStats(String userId) {
        List<EmailEntity> allEmails = emailRepository.findByUserIdOrderByReceivedTimeDesc(userId);
        
        long totalAutoResponded = allEmails.stream()
                .filter(email -> Boolean.TRUE.equals(email.getAutoResponseSent()))
                .count();
        
        long pendingAutoResponse = allEmails.stream()
                .filter(email -> Boolean.FALSE.equals(email.getRequiresAttention()) && 
                               Boolean.FALSE.equals(email.getAutoResponseSent()))
                .count();
        
        AutoResponseStats stats = new AutoResponseStats();
        stats.setTotalAutoResponded(totalAutoResponded);
        stats.setPendingAutoResponse(pendingAutoResponse);
        
        return stats;
    }
    
    // Inner class for auto-response statistics
    public static class AutoResponseStats {
        private long totalAutoResponded;
        private long pendingAutoResponse;
        
        public long getTotalAutoResponded() { return totalAutoResponded; }
        public void setTotalAutoResponded(long totalAutoResponded) { this.totalAutoResponded = totalAutoResponded; }
        
        public long getPendingAutoResponse() { return pendingAutoResponse; }
        public void setPendingAutoResponse(long pendingAutoResponse) { this.pendingAutoResponse = pendingAutoResponse; }
    }
}
