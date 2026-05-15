package com.intelligentassistant.emailassistant.llm;

import com.intelligentassistant.emailassistant.model.EmailAnalysisRequest;
import com.intelligentassistant.emailassistant.model.EmailAnalysisResponse;
import reactor.core.publisher.Mono;

/**
 * Interface for different LLM providers (OpenAI, DeepSeek, etc.)
 */
public interface LLMProvider {
    
    /**
     * Analyzes an email and determines if personal attention is required
     * @param request Email analysis request containing email content and context
     * @return Analysis response with decision and generated response
     */
    Mono<EmailAnalysisResponse> analyzeEmail(EmailAnalysisRequest request);
    
    /**
     * Generates a response to an email based on historical patterns
     * @param request Email content and historical response patterns
     * @return Generated email response
     */
    Mono<String> generateResponse(EmailAnalysisRequest request);
    
    /**
     * Gets the provider name
     * @return Provider identifier
     */
    String getProviderName();
    
    /**
     * Checks if the provider is available
     * @return true if provider can be used
     */
    Mono<Boolean> isAvailable();
}
