package com.intelligentassistant.emailassistant.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;

/**
 * Email entity for database storage
 */
@Entity
@Table(name = "emails")
public class EmailEntity {
    
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private String id;
    
    @Column(name = "email_id", unique = true, nullable = false)
    private String emailId; // Microsoft Graph email ID
    
    @Column(name = "user_id", nullable = false)
    private String userId;
    
    @Column(name = "subject")
    private String subject;
    
    @Column(name = "content", columnDefinition = "TEXT")
    private String content;
    
    @Column(name = "sender_email")
    private String senderEmail;
    
    @Column(name = "sender_name")
    private String senderName;
    
    @Column(name = "received_time")
    private LocalDateTime receivedTime;
    
    @Column(name = "processed_time")
    private LocalDateTime processedTime;
    
    @Column(name = "requires_attention")
    private Boolean requiresAttention;
    
    @Column(name = "confidence_score")
    private Double confidenceScore;
    
    @Column(name = "category")
    private String category;
    
    @Column(name = "sentiment")
    private String sentiment;
    
    @Column(name = "llm_provider")
    private String llmProvider;
    
    @Column(name = "processing_status")
    @Enumerated(EnumType.STRING)
    private ProcessingStatus processingStatus;
    
    @Column(name = "whatsapp_sent")
    private Boolean whatsappSent;
    
    @Column(name = "auto_response_sent")
    private Boolean autoResponseSent;
    
    @Column(name = "created_at")
    private LocalDateTime createdAt;
    
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;
    
    // Constructors
    public EmailEntity() {}
    
    public EmailEntity(String emailId, String userId, String subject, String content, 
                      String senderEmail, String senderName, LocalDateTime receivedTime) {
        this.emailId = emailId;
        this.userId = userId;
        this.subject = subject;
        this.content = content;
        this.senderEmail = senderEmail;
        this.senderName = senderName;
        this.receivedTime = receivedTime;
        this.processingStatus = ProcessingStatus.PENDING;
        this.whatsappSent = false;
        this.autoResponseSent = false;
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }
    
    @PreUpdate
    protected void onUpdate() {
        updatedAt = LocalDateTime.now();
    }
    
    // Getters and Setters
    public String getId() {
        return id;
    }
    
    public void setId(String id) {
        this.id = id;
    }
    
    public String getEmailId() {
        return emailId;
    }
    
    public void setEmailId(String emailId) {
        this.emailId = emailId;
    }
    
    public String getUserId() {
        return userId;
    }
    
    public void setUserId(String userId) {
        this.userId = userId;
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
    
    public LocalDateTime getProcessedTime() {
        return processedTime;
    }
    
    public void setProcessedTime(LocalDateTime processedTime) {
        this.processedTime = processedTime;
    }
    
    public Boolean getRequiresAttention() {
        return requiresAttention;
    }
    
    public void setRequiresAttention(Boolean requiresAttention) {
        this.requiresAttention = requiresAttention;
    }
    
    public Double getConfidenceScore() {
        return confidenceScore;
    }
    
    public void setConfidenceScore(Double confidenceScore) {
        this.confidenceScore = confidenceScore;
    }
    
    public String getCategory() {
        return category;
    }
    
    public void setCategory(String category) {
        this.category = category;
    }
    
    public String getSentiment() {
        return sentiment;
    }
    
    public void setSentiment(String sentiment) {
        this.sentiment = sentiment;
    }
    
    public String getLlmProvider() {
        return llmProvider;
    }
    
    public void setLlmProvider(String llmProvider) {
        this.llmProvider = llmProvider;
    }
    
    public ProcessingStatus getProcessingStatus() {
        return processingStatus;
    }
    
    public void setProcessingStatus(ProcessingStatus processingStatus) {
        this.processingStatus = processingStatus;
    }
    
    public Boolean getWhatsappSent() {
        return whatsappSent;
    }
    
    public void setWhatsappSent(Boolean whatsappSent) {
        this.whatsappSent = whatsappSent;
    }
    
    public Boolean getAutoResponseSent() {
        return autoResponseSent;
    }
    
    public void setAutoResponseSent(Boolean autoResponseSent) {
        this.autoResponseSent = autoResponseSent;
    }
    
    public LocalDateTime getCreatedAt() {
        return createdAt;
    }
    
    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }
    
    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }
    
    public void setUpdatedAt(LocalDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }
    
    public enum ProcessingStatus {
        PENDING, PROCESSING, COMPLETED, FAILED
    }
}
