package com.intelligentassistant.emailassistant.service;

import com.intelligentassistant.emailassistant.llm.LLMProvider;
import com.intelligentassistant.emailassistant.model.EmailAnalysisRequest;
import com.intelligentassistant.emailassistant.model.EmailAnalysisResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * Service to manage multiple LLM providers and route requests
 */
@Service
public class LLMService {
    
    private static final Logger logger = LoggerFactory.getLogger(LLMService.class);
    
    @Value("${app.llm.default-provider}")
    private String defaultProvider;
    
    private final Map<String, LLMProvider> providers;
    
    public LLMService(List<LLMProvider> providerList) {
        this.providers = providerList.stream()
                .collect(Collectors.toMap(LLMProvider::getProviderName, Function.identity()));
        
        logger.info("Initialized LLM service with providers: {}", providers.keySet());
    }
    
    /**
     * Analyzes an email using the specified or default provider
     */
    public Mono<EmailAnalysisResponse> analyzeEmail(EmailAnalysisRequest request, String providerName) {
        LLMProvider provider = getProvider(providerName);
        if (provider == null) {
            return Mono.error(new IllegalArgumentException("Provider not found: " + providerName));
        }
        
        return provider.isAvailable()
                .flatMap(available -> {
                    if (!available) {
                        logger.warn("Provider {} is not available, falling back to default", providerName);
                        return getNextAvailableProvider()
                                .flatMap(fallbackProvider -> fallbackProvider.analyzeEmail(request));
                    }
                    return provider.analyzeEmail(request);
                })
                .doOnNext(response -> logger.info("Email analysis completed with provider: {}", provider.getProviderName()))
                .doOnError(error -> logger.error("Error analyzing email with provider: " + provider.getProviderName(), error));
    }
    
    /**
     * Analyzes an email using the default provider
     */
    public Mono<EmailAnalysisResponse> analyzeEmail(EmailAnalysisRequest request) {
        return analyzeEmail(request, defaultProvider);
    }
    
    /**
     * Generates a response using the specified or default provider
     */
    public Mono<String> generateResponse(EmailAnalysisRequest request, String providerName) {
        LLMProvider provider = getProvider(providerName);
        if (provider == null) {
            return Mono.error(new IllegalArgumentException("Provider not found: " + providerName));
        }
        
        return provider.isAvailable()
                .flatMap(available -> {
                    if (!available) {
                        logger.warn("Provider {} is not available, falling back to default", providerName);
                        return getNextAvailableProvider()
                                .flatMap(fallbackProvider -> fallbackProvider.generateResponse(request));
                    }
                    return provider.generateResponse(request);
                })
                .doOnNext(response -> logger.info("Response generation completed with provider: {}", provider.getProviderName()))
                .doOnError(error -> logger.error("Error generating response with provider: " + provider.getProviderName(), error));
    }
    
    /**
     * Generates a response using the default provider
     */
    public Mono<String> generateResponse(EmailAnalysisRequest request) {
        return generateResponse(request, defaultProvider);
    }
    
    /**
     * Gets the status of all providers
     */
    public Mono<Map<String, Boolean>> getProvidersStatus() {
        return Mono.fromCallable(() -> {
            return providers.entrySet().stream()
                    .collect(Collectors.toMap(
                            Map.Entry::getKey,
                            entry -> entry.getValue().isAvailable().block()
                    ));
        });
    }
    
    /**
     * Gets available provider names
     */
    public List<String> getAvailableProviders() {
        return providers.keySet().stream().collect(Collectors.toList());
    }
    
    /**
     * Checks if a provider is available
     */
    public Mono<Boolean> isProviderAvailable(String providerName) {
        LLMProvider provider = getProvider(providerName);
        if (provider == null) {
            return Mono.just(false);
        }
        return provider.isAvailable();
    }
    
    private LLMProvider getProvider(String providerName) {
        if (providerName == null) {
            providerName = defaultProvider;
        }
        return providers.get(providerName);
    }
    
    private Mono<LLMProvider> getNextAvailableProvider() {
        return Mono.fromCallable(() -> {
            // First try default provider
            LLMProvider defaultProv = providers.get(defaultProvider);
            if (defaultProv != null && Boolean.TRUE.equals(defaultProv.isAvailable().block())) {
                return defaultProv;
            }
            
            // Try other providers
            Optional<LLMProvider> availableProvider = providers.values().stream()
                    .filter(provider -> Boolean.TRUE.equals(provider.isAvailable().block()))
                    .findFirst();
            
            if (availableProvider.isPresent()) {
                return availableProvider.get();
            }
            
            throw new RuntimeException("No LLM providers are available");
        });
    }
}
