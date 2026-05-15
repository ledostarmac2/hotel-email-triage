package com.intelligentassistant.emailassistant.model;

import java.time.LocalDateTime;
import java.util.List;

/**
 * Request model for email analysis
 */
public class EmailAnalysisRequest {
    private String emailId;
    private String subject;
    private String content;
    private String senderEmail;
    private String senderName;
    private LocalDateTime receivedTime;
    private List<String> historicalResponses;
    private UserPreferences userPreferences;
    private String conversationContext;
    
    // Constructors
    public EmailAnalysisRequest() {}
    
    public EmailAnalysisRequest(String emailId, String subject, String content, 
                               String senderEmail, String senderName, LocalDateTime receivedTime) {
        this.emailId = emailId;
        this.subject = subject;
        this.content = content;
        this.senderEmail = senderEmail;
        this.senderName = senderName;
        this.receivedTime = receivedTime;
    }
    
    // Getters and Setters
    public String getEmailId() {
        return emailId;
    }
    
    public void setEmailId(String emailId) {
        this.emailId = emailId;
    }
    
    public String getSubject() {
        return subject;
    }
    
    public void setSubject(String subject) {
        this.subject = subject;
    }
    
    public String getContent() {
        return content;
    }
    
    public void setContent(String content) {
        this.content = content;
    }
    
    public String getSenderEmail() {
        return senderEmail;
    }
    
    public void setSenderEmail(String senderEmail) {
        this.senderEmail = senderEmail;
    }
    
    public String getSenderName() {
        return senderName;
    }
    
    public void setSenderName(String senderName) {
        this.senderName = senderName;
    }
    
    public LocalDateTime getReceivedTime() {
        return receivedTime;
    }
    
    public void setReceivedTime(LocalDateTime receivedTime) {
        this.receivedTime = receivedTime;
    }
    
    public List<String> getHistoricalResponses() {
        return historicalResponses;
    }
    
    public void setHistoricalResponses(List<String> historicalResponses) {
        this.historicalResponses = historicalResponses;
    }
    
    public UserPreferences getUserPreferences() {
        return userPreferences;
    }
    
    public void setUserPreferences(UserPreferences userPreferences) {
        this.userPreferences = userPreferences;
    }
    
    public String getConversationContext() {
        return conversationContext;
    }
    
    public void setConversationContext(String conversationContext) {
        this.conversationContext = conversationContext;
    }
}
