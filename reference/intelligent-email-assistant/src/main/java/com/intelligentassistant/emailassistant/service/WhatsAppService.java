package com.intelligentassistant.emailassistant.service;

import com.twilio.Twilio;
import com.twilio.rest.api.v2010.account.Message;
import com.twilio.type.PhoneNumber;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;

/**
 * Service for sending WhatsApp notifications using Twilio
 */
@Service
public class WhatsAppService {
    
    private static final Logger logger = LoggerFactory.getLogger(WhatsAppService.class);
    
    @Value("${app.whatsapp.twilio.account-sid}")
    private String accountSid;
    
    @Value("${app.whatsapp.twilio.auth-token}")
    private String authToken;
    
    @Value("${app.whatsapp.twilio.from-number}")
    private String fromNumber;
    
    @PostConstruct
    public void initializeTwilio() {
        try {
            Twilio.init(accountSid, authToken);
            logger.info("Twilio WhatsApp service initialized successfully");
        } catch (Exception e) {
            logger.error("Failed to initialize Twilio WhatsApp service", e);
        }
    }
    
    /**
     * Send WhatsApp notification about email requiring attention
     */
    public boolean sendEmailNotification(String toNumber, String senderName, String subject, String reason) {
        try {
            String messageBody = buildEmailNotificationMessage(senderName, subject, reason);
            return sendWhatsAppMessage(toNumber, messageBody);
        } catch (Exception e) {
            logger.error("Error sending email notification to: " + toNumber, e);
            return false;
        }
    }
    
    /**
     * Send custom WhatsApp message
     */
    public boolean sendWhatsAppMessage(String toNumber, String messageBody) {
        try {
            // Ensure the number is in WhatsApp format
            String whatsappTo = formatWhatsAppNumber(toNumber);
            String whatsappFrom = formatWhatsAppNumber(fromNumber);
            
            Message message = Message.creator(
                    new PhoneNumber(whatsappTo),
                    new PhoneNumber(whatsappFrom),
                    messageBody
            ).create();
            
            logger.info("WhatsApp message sent successfully. SID: {}", message.getSid());
            return true;
            
        } catch (Exception e) {
            logger.error("Error sending WhatsApp message to: " + toNumber, e);
            return false;
        }
    }
    
    /**
     * Send daily summary notification
     */
    public boolean sendDailySummary(String toNumber, int totalEmails, int requireAttention, int autoResponded) {
        try {
            String messageBody = buildDailySummaryMessage(totalEmails, requireAttention, autoResponded);
            return sendWhatsAppMessage(toNumber, messageBody);
        } catch (Exception e) {
            logger.error("Error sending daily summary to: " + toNumber, e);
            return false;
        }
    }
    
    /**
     * Send system alert notification
     */
    public boolean sendSystemAlert(String toNumber, String alertType, String message) {
        try {
            String messageBody = buildSystemAlertMessage(alertType, message);
            return sendWhatsAppMessage(toNumber, messageBody);
        } catch (Exception e) {
            logger.error("Error sending system alert to: " + toNumber, e);
            return false;
        }
    }
    
    /**
     * Test WhatsApp connectivity
     */
    public boolean testConnection(String toNumber) {
        try {
            String testMessage = "🤖 *Email Assistant Test*\n\n" +
                    "This is a test message from your Intelligent Email Assistant. " +
                    "If you receive this, the WhatsApp integration is working correctly!\n\n" +
                    "🕒 " + java.time.LocalDateTime.now().toString();
            
            return sendWhatsAppMessage(toNumber, testMessage);
        } catch (Exception e) {
            logger.error("Error testing WhatsApp connection to: " + toNumber, e);
            return false;
        }
    }
    
    private String buildEmailNotificationMessage(String senderName, String subject, String reason) {
        StringBuilder message = new StringBuilder();
        message.append("📧 *Important Email Alert*\n\n");
        message.append("**From:** ").append(senderName != null ? senderName : "Unknown Sender").append("\n");
        message.append("**Subject:** ").append(subject != null ? truncateText(subject, 50) : "No Subject").append("\n\n");
        message.append("**Why it needs your attention:**\n");
        message.append(reason != null ? reason : "Requires personal review").append("\n\n");
        message.append("🔗 Check your email to respond\n");
        message.append("🕒 ").append(java.time.LocalDateTime.now().format(java.time.format.DateTimeFormatter.ofPattern("MMM dd, yyyy HH:mm")));
        
        return message.toString();
    }
    
    private String buildDailySummaryMessage(int totalEmails, int requireAttention, int autoResponded) {
        StringBuilder message = new StringBuilder();
        message.append("📊 *Daily Email Summary*\n\n");
        message.append("📬 **Total emails processed:** ").append(totalEmails).append("\n");
        message.append("⚠️ **Require your attention:** ").append(requireAttention).append("\n");
        message.append("🤖 **Auto-responded:** ").append(autoResponded).append("\n\n");
        
        if (requireAttention > 0) {
            message.append("💡 You have ").append(requireAttention).append(" email");
            if (requireAttention > 1) message.append("s");
            message.append(" waiting for your review.\n\n");
        } else {
            message.append("✅ All emails have been handled automatically!\n\n");
        }
        
        message.append("🕒 ").append(java.time.LocalDate.now().format(java.time.format.DateTimeFormatter.ofPattern("MMM dd, yyyy")));
        
        return message.toString();
    }
    
    private String buildSystemAlertMessage(String alertType, String alertMessage) {
        StringBuilder message = new StringBuilder();
        message.append("🚨 *System Alert*\n\n");
        message.append("**Type:** ").append(alertType).append("\n");
        message.append("**Details:** ").append(alertMessage).append("\n\n");
        message.append("🛠️ Please check the system logs for more information.\n");
        message.append("🕒 ").append(java.time.LocalDateTime.now().format(java.time.format.DateTimeFormatter.ofPattern("MMM dd, yyyy HH:mm")));
        
        return message.toString();
    }
    
    private String formatWhatsAppNumber(String phoneNumber) {
        if (phoneNumber == null || phoneNumber.trim().isEmpty()) {
            throw new IllegalArgumentException("Phone number cannot be null or empty");
        }
        
        // Remove any non-digit characters except +
        String cleaned = phoneNumber.replaceAll("[^\\d+]", "");
        
        // Ensure it starts with whatsapp: prefix for Twilio
        if (!cleaned.startsWith("whatsapp:")) {
            if (!cleaned.startsWith("+")) {
                cleaned = "+" + cleaned;
            }
            cleaned = "whatsapp:" + cleaned;
        }
        
        return cleaned;
    }
    
    private String truncateText(String text, int maxLength) {
        if (text == null || text.length() <= maxLength) {
            return text;
        }
        return text.substring(0, maxLength - 3) + "...";
    }
    
    /**
     * Check if WhatsApp service is configured properly
     */
    public boolean isConfigured() {
        return accountSid != null && !accountSid.trim().isEmpty() &&
               authToken != null && !authToken.trim().isEmpty() &&
               fromNumber != null && !fromNumber.trim().isEmpty();
    }
}
