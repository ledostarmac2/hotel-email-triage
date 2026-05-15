package com.intelligentassistant.emailassistant.model;

import java.util.List;

/**
 * User preferences for email analysis and response generation
 */
public class UserPreferences {
    private String userId;
    private String responseStyle; // formal, casual, friendly, professional
    private List<String> keywordsRequiringAttention;
    private List<String> trustedSenders;
    private List<String> autoRespondSenders;
    private boolean enableWhatsAppNotifications;
    private String whatsAppNumber;
    private int responseDelayMinutes;
    private String timezone;
    private List<String> workingHours;
    
    // Constructors
    public UserPreferences() {}
    
    public UserPreferences(String userId) {
        this.userId = userId;
    }
    
    // Getters and Setters
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
    
    public List<String> getKeywordsRequiringAttention() {
        return keywordsRequiringAttention;
    }
    
    public void setKeywordsRequiringAttention(List<String> keywordsRequiringAttention) {
        this.keywordsRequiringAttention = keywordsRequiringAttention;
    }
    
    public List<String> getTrustedSenders() {
        return trustedSenders;
    }
    
    public void setTrustedSenders(List<String> trustedSenders) {
        this.trustedSenders = trustedSenders;
    }
    
    public List<String> getAutoRespondSenders() {
        return autoRespondSenders;
    }
    
    public void setAutoRespondSenders(List<String> autoRespondSenders) {
        this.autoRespondSenders = autoRespondSenders;
    }
    
    public boolean isEnableWhatsAppNotifications() {
        return enableWhatsAppNotifications;
    }
    
    public void setEnableWhatsAppNotifications(boolean enableWhatsAppNotifications) {
        this.enableWhatsAppNotifications = enableWhatsAppNotifications;
    }
    
    public String getWhatsAppNumber() {
        return whatsAppNumber;
    }
    
    public void setWhatsAppNumber(String whatsAppNumber) {
        this.whatsAppNumber = whatsAppNumber;
    }
    
    public int getResponseDelayMinutes() {
        return responseDelayMinutes;
    }
    
    public void setResponseDelayMinutes(int responseDelayMinutes) {
        this.responseDelayMinutes = responseDelayMinutes;
    }
    
    public String getTimezone() {
        return timezone;
    }
    
    public void setTimezone(String timezone) {
        this.timezone = timezone;
    }
    
    public List<String> getWorkingHours() {
        return workingHours;
    }
    
    public void setWorkingHours(List<String> workingHours) {
        this.workingHours = workingHours;
    }
}
