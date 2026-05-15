package com.intelligentassistant.emailassistant.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;
import java.util.List;

/**
 * User preferences entity for database storage
 */
@Entity
@Table(name = "user_preferences")
public class UserPreferencesEntity {
    
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private String id;
    
    @Column(name = "user_id", unique = true, nullable = false)
    private String userId;
    
    @Column(name = "response_style")
    private String responseStyle;
    
    @Column(name = "keywords_requiring_attention", columnDefinition = "TEXT")
    private String keywordsRequiringAttention; // JSON array stored as text
    
    @Column(name = "trusted_senders", columnDefinition = "TEXT")
    private String trustedSenders; // JSON array stored as text
    
    @Column(name = "auto_respond_senders", columnDefinition = "TEXT")
    private String autoRespondSenders; // JSON array stored as text
    
    @Column(name = "enable_whatsapp_notifications")
    private Boolean enableWhatsAppNotifications;
    
    @Column(name = "whatsapp_number")
    private String whatsAppNumber;
    
    @Column(name = "response_delay_minutes")
    private Integer responseDelayMinutes;
    
    @Column(name = "timezone")
    private String timezone;
    
    @Column(name = "working_hours", columnDefinition = "TEXT")
    private String workingHours; // JSON array stored as text
    
    @Column(name = "default_llm_provider")
    private String defaultLlmProvider;
    
    @Column(name = "confidence_threshold")
    private Double confidenceThreshold;
    
    @Column(name = "created_at")
    private LocalDateTime createdAt;
    
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;
    
    // Constructors
    public UserPreferencesEntity() {}
    
    public UserPreferencesEntity(String userId) {
        this.userId = userId;
        this.responseStyle = "professional";
        this.enableWhatsAppNotifications = true;
        this.responseDelayMinutes = 5;
        this.timezone = "UTC";
        this.defaultLlmProvider = "openai";
        this.confidenceThreshold = 0.7;
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
    
    public String getUserId() {
        return userId;
    }
    
    public void setUserId(String userId) {
        this.userId = userId;
    }
    
    public String getResponseStyle() {
        return responseStyle;
    }
    
    public void setResponseStyle(String responseStyle) {
        this.responseStyle = responseStyle;
    }
    
    public String getKeywordsRequiringAttention() {
        return keywordsRequiringAttention;
    }
    
    public void setKeywordsRequiringAttention(String keywordsRequiringAttention) {
        this.keywordsRequiringAttention = keywordsRequiringAttention;
    }
    
    public String getTrustedSenders() {
        return trustedSenders;
    }
    
    public void setTrustedSenders(String trustedSenders) {
        this.trustedSenders = trustedSenders;
    }
    
    public String getAutoRespondSenders() {
        return autoRespondSenders;
    }
    
    public void setAutoRespondSenders(String autoRespondSenders) {
        this.autoRespondSenders = autoRespondSenders;
    }
    
    public Boolean getEnableWhatsAppNotifications() {
        return enableWhatsAppNotifications;
    }
    
    public void setEnableWhatsAppNotifications(Boolean enableWhatsAppNotifications) {
        this.enableWhatsAppNotifications = enableWhatsAppNotifications;
    }
    
    public String getWhatsAppNumber() {
        return whatsAppNumber;
    }
    
    public void setWhatsAppNumber(String whatsAppNumber) {
        this.whatsAppNumber = whatsAppNumber;
    }
    
    public Integer getResponseDelayMinutes() {
        return responseDelayMinutes;
    }
    
    public void setResponseDelayMinutes(Integer responseDelayMinutes) {
        this.responseDelayMinutes = responseDelayMinutes;
    }
    
    public String getTimezone() {
        return timezone;
    }
    
    public void setTimezone(String timezone) {
        this.timezone = timezone;
    }
    
    public String getWorkingHours() {
        return workingHours;
    }
    
    public void setWorkingHours(String workingHours) {
        this.workingHours = workingHours;
    }
    
    public String getDefaultLlmProvider() {
        return defaultLlmProvider;
    }
    
    public void setDefaultLlmProvider(String defaultLlmProvider) {
        this.defaultLlmProvider = defaultLlmProvider;
    }
    
    public Double getConfidenceThreshold() {
        return confidenceThreshold;
    }
    
    public void setConfidenceThreshold(Double confidenceThreshold) {
        this.confidenceThreshold = confidenceThreshold;
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
}
