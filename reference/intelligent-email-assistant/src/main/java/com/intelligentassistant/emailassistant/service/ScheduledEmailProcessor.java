package com.intelligentassistant.emailassistant.service;

import com.intelligentassistant.emailassistant.model.EmailAnalysisRequest;
import com.intelligentassistant.emailassistant.model.EmailEntity;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * Scheduled service for processing emails in batches
 */
@Service
public class ScheduledEmailProcessor {
    
    private static final Logger logger = LoggerFactory.getLogger(ScheduledEmailProcessor.class);
    
    @Value("${app.email.batch-size}")
    private int batchSize;
    
    @Value("${app.email.check-interval-minutes}")
    private int checkIntervalMinutes;
    
    // For demo purposes, we'll use a hardcoded user ID
    // In production, this would iterate through all users
    private static final String DEMO_USER_ID = "demo-user-123";
    
    private final MicrosoftGraphService microsoftGraphService;
    private final EmailAnalysisService emailAnalysisService;
    private final AutoResponseService autoResponseService;
    private LocalDateTime lastCheckTime;
    
    public ScheduledEmailProcessor(MicrosoftGraphService microsoftGraphService,
                                  EmailAnalysisService emailAnalysisService,
                                  AutoResponseService autoResponseService) {
        this.microsoftGraphService = microsoftGraphService;
        this.emailAnalysisService = emailAnalysisService;
        this.autoResponseService = autoResponseService;
        this.lastCheckTime = LocalDateTime.now().minusHours(1); // Start by checking last hour
    }
    
    /**
     * Scheduled task to process new emails
     * Runs every 5 minutes by default
     */
    @Scheduled(fixedRateString = "${app.email.check-interval-minutes:5}", timeUnit = TimeUnit.MINUTES)
    public void processNewEmails() {
        logger.info("Starting scheduled email processing...");
        
        try {
            // Check if Microsoft Graph service is initialized
            if (!microsoftGraphService.isInitialized()) {
                logger.warn("Microsoft Graph service not initialized, skipping email processing");
                return;
            }
            
            // Get new emails since last check (using simplified stub service)
            List<EmailAnalysisRequest> analysisRequests = microsoftGraphService.getEmailsAfter(lastCheckTime, batchSize);
            
            if (analysisRequests.isEmpty()) {
                logger.info("No new emails found since last check: {}", lastCheckTime);
                updateLastCheckTime();
                return;
            }
            
            logger.info("Found {} new emails to process", analysisRequests.size());
            
            // Process emails in batch
            List<EmailEntity> processedEmails = emailAnalysisService
                    .processEmailsBatch(analysisRequests, DEMO_USER_ID)
                    .block();
            
            logger.info("Successfully processed {} emails", processedEmails != null ? processedEmails.size() : 0);
            
            // Send notifications for emails requiring attention
            emailAnalysisService.sendNotifications(DEMO_USER_ID).block();
            
            updateLastCheckTime();
            
        } catch (Exception e) {
            logger.error("Error during scheduled email processing", e);
        }
    }
    
    /**
     * Scheduled task to process auto-responses
     * Runs every 10 minutes
     */
    @Scheduled(fixedRate = 10, timeUnit = TimeUnit.MINUTES)
    public void processAutoResponses() {
        logger.info("Starting scheduled auto-response processing...");
        
        try {
            Integer responsesGenerated = autoResponseService.processAutoResponses(DEMO_USER_ID).block();
            
            if (responsesGenerated != null && responsesGenerated > 0) {
                logger.info("Generated {} auto-responses", responsesGenerated);
            } else {
                logger.info("No auto-responses were generated");
            }
            
        } catch (Exception e) {
            logger.error("Error during auto-response processing", e);
        }
    }
    
    /**
     * Scheduled task to send daily summary
     * Runs daily at 8 PM
     */
    @Scheduled(cron = "0 0 20 * * ?")
    public void sendDailySummary() {
        logger.info("Starting daily summary generation...");
        
        try {
            EmailAnalysisService.EmailStats stats = emailAnalysisService.getEmailStats(DEMO_USER_ID);
            
            // Get WhatsApp service to send summary
            // This would typically get the user's WhatsApp number from preferences
            String whatsappNumber = "+1234567890"; // Placeholder - should come from user preferences
            
            // Send daily summary (implement this method in WhatsAppService if needed)
            logger.info("Daily Summary - Total: {}, Requiring Attention: {}, Auto-Responded: {}", 
                       stats.getTotalProcessed(), 
                       stats.getRequiringAttention(), 
                       stats.getAutoResponded());
            
        } catch (Exception e) {
            logger.error("Error during daily summary generation", e);
        }
    }
    
    /**
     * Scheduled task for system health checks
     * Runs every hour
     */
    @Scheduled(fixedRate = 1, timeUnit = TimeUnit.HOURS)
    public void performHealthCheck() {
        logger.debug("Performing system health check...");
        
        try {
            // Check Microsoft Graph connectivity
            boolean graphHealthy = checkMicrosoftGraphHealth();
            
            // Check LLM providers
            boolean llmHealthy = checkLLMProvidersHealth();
            
            // Check WhatsApp service
            boolean whatsappHealthy = checkWhatsAppHealth();
            
            if (!graphHealthy || !llmHealthy || !whatsappHealthy) {
                logger.warn("System health check failed - Graph: {}, LLM: {}, WhatsApp: {}", 
                           graphHealthy, llmHealthy, whatsappHealthy);
                
                // Could send alert via WhatsApp here
                // whatsAppService.sendSystemAlert(userPhoneNumber, "Health Check", "System components are experiencing issues");
            } else {
                logger.debug("System health check passed");
            }
            
        } catch (Exception e) {
            logger.error("Error during system health check", e);
        }
    }
    
    /**
     * Manual trigger for processing emails (for testing)
     */
    public void triggerEmailProcessing() {
        logger.info("Manually triggered email processing");
        processNewEmails();
    }
    
    /**
     * Manual trigger for auto-responses (for testing)
     */
    public void triggerAutoResponseProcessing() {
        logger.info("Manually triggered auto-response processing");
        processAutoResponses();
    }
    
    private void updateLastCheckTime() {
        this.lastCheckTime = LocalDateTime.now();
        logger.debug("Updated last check time to: {}", lastCheckTime);
    }
    
    private boolean checkMicrosoftGraphHealth() {
        try {
            return microsoftGraphService.isInitialized();
        } catch (Exception e) {
            logger.warn("Microsoft Graph health check failed", e);
            return false;
        }
    }
    
    private boolean checkLLMProvidersHealth() {
        try {
            // This would check if LLM providers are responding
            // For now, just return true
            return true;
        } catch (Exception e) {
            logger.warn("LLM providers health check failed", e);
            return false;
        }
    }
    
    private boolean checkWhatsAppHealth() {
        try {
            // This would check WhatsApp/Twilio connectivity
            // For now, just return true
            return true;
        } catch (Exception e) {
            logger.warn("WhatsApp health check failed", e);
            return false;
        }
    }
    
    /**
     * Get processing statistics
     */
    public ProcessingStats getProcessingStats() {
        ProcessingStats stats = new ProcessingStats();
        stats.setLastCheckTime(lastCheckTime);
        stats.setBatchSize(batchSize);
        stats.setCheckIntervalMinutes(checkIntervalMinutes);
        
        // Add more statistics as needed
        return stats;
    }
    
    // Inner class for processing statistics
    public static class ProcessingStats {
        private LocalDateTime lastCheckTime;
        private int batchSize;
        private int checkIntervalMinutes;
        
        public LocalDateTime getLastCheckTime() { return lastCheckTime; }
        public void setLastCheckTime(LocalDateTime lastCheckTime) { this.lastCheckTime = lastCheckTime; }
        
        public int getBatchSize() { return batchSize; }
        public void setBatchSize(int batchSize) { this.batchSize = batchSize; }
        
        public int getCheckIntervalMinutes() { return checkIntervalMinutes; }
        public void setCheckIntervalMinutes(int checkIntervalMinutes) { this.checkIntervalMinutes = checkIntervalMinutes; }
    }
}
