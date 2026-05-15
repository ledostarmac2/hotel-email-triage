package com.intelligentassistant.emailassistant.model;

/**
 * Response model for email analysis
 */
public class EmailAnalysisResponse {
    private boolean requiresPersonalAttention;
    private double confidenceScore;
    private String reasonForDecision;
    private String generatedResponse;
    private String recommendedAction;
    private String category;
    private String sentiment;
    
    // Constructors
    public EmailAnalysisResponse() {}
    
    public EmailAnalysisResponse(boolean requiresPersonalAttention, double confidenceScore, 
                                String reasonForDecision, String generatedResponse) {
        this.requiresPersonalAttention = requiresPersonalAttention;
        this.confidenceScore = confidenceScore;
        this.reasonForDecision = reasonForDecision;
        this.generatedResponse = generatedResponse;
    }
    
    // Getters and Setters
    public boolean isRequiresPersonalAttention() {
        return requiresPersonalAttention;
    }
    
    public void setRequiresPersonalAttention(boolean requiresPersonalAttention) {
        this.requiresPersonalAttention = requiresPersonalAttention;
    }
    
    public double getConfidenceScore() {
        return confidenceScore;
    }
    
    public void setConfidenceScore(double confidenceScore) {
        this.confidenceScore = confidenceScore;
    }
    
    public String getReasonForDecision() {
        return reasonForDecision;
    }
    
    public void setReasonForDecision(String reasonForDecision) {
        this.reasonForDecision = reasonForDecision;
    }
    
    public String getGeneratedResponse() {
        return generatedResponse;
    }
    
    public void setGeneratedResponse(String generatedResponse) {
        this.generatedResponse = generatedResponse;
    }
    
    public String getRecommendedAction() {
        return recommendedAction;
    }
    
    public void setRecommendedAction(String recommendedAction) {
        this.recommendedAction = recommendedAction;
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
}
