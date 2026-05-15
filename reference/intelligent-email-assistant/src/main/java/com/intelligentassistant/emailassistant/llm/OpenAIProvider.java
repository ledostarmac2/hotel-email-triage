package com.intelligentassistant.emailassistant.llm;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.intelligentassistant.emailassistant.model.EmailAnalysisRequest;
import com.intelligentassistant.emailassistant.model.EmailAnalysisResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

/**
 * OpenAI GPT provider implementation
 */
@Component
public class OpenAIProvider implements LLMProvider {
    
    private static final Logger logger = LoggerFactory.getLogger(OpenAIProvider.class);
    
    @Value("${app.llm.openai.api-key}")
    private String apiKey;
    
    @Value("${app.llm.openai.base-url}")
    private String baseUrl;
    
    @Value("${app.llm.openai.model}")
    private String model;
    
    private final WebClient webClient;
    private final ObjectMapper objectMapper;
    
    public OpenAIProvider(WebClient.Builder webClientBuilder, ObjectMapper objectMapper) {
        this.webClient = webClientBuilder.build();
        this.objectMapper = objectMapper;
    }
    
    @Override
    public Mono<EmailAnalysisResponse> analyzeEmail(EmailAnalysisRequest request) {
        String systemPrompt = buildAnalysisPrompt(request);
        String userMessage = formatEmailForAnalysis(request);
        
        return callOpenAI(systemPrompt, userMessage)
                .map(this::parseAnalysisResponse)
                .doOnError(error -> logger.error("Error analyzing email with OpenAI", error));
    }
    
    @Override
    public Mono<String> generateResponse(EmailAnalysisRequest request) {
        String systemPrompt = buildResponsePrompt(request);
        String userMessage = formatEmailForResponse(request);
        
        return callOpenAI(systemPrompt, userMessage)
                .map(response -> extractContentFromResponse(response))
                .doOnError(error -> logger.error("Error generating response with OpenAI", error));
    }
    
    @Override
    public String getProviderName() {
        return "openai";
    }
    
    @Override
    public Mono<Boolean> isAvailable() {
        return Mono.fromCallable(() -> apiKey != null && !apiKey.trim().isEmpty())
                .onErrorReturn(false);
    }
    
    private Mono<String> callOpenAI(String systemPrompt, String userMessage) {
        OpenAIRequest openAIRequest = new OpenAIRequest();
        openAIRequest.model = model;
        openAIRequest.messages = List.of(
                new Message("system", systemPrompt),
                new Message("user", userMessage)
        );
        openAIRequest.maxTokens = 1000;
        openAIRequest.temperature = 0.7;
        
        return webClient.post()
                .uri(baseUrl + "/chat/completions")
                .header("Authorization", "Bearer " + apiKey)
                .header("Content-Type", "application/json")
                .bodyValue(openAIRequest)
                .retrieve()
                .bodyToMono(String.class);
    }
    
    private String buildAnalysisPrompt(EmailAnalysisRequest request) {
        StringBuilder prompt = new StringBuilder();
        prompt.append("You are an intelligent email assistant. Analyze the following email and determine:\n");
        prompt.append("1. Whether it requires personal attention from the user\n");
        prompt.append("2. The confidence level of your decision (0.0 to 1.0)\n");
        prompt.append("3. The reason for your decision\n");
        prompt.append("4. Generate an appropriate response if it doesn't need personal attention\n");
        prompt.append("5. Categorize the email (business, personal, spam, newsletter, etc.)\n");
        prompt.append("6. Determine the sentiment (positive, negative, neutral, urgent)\n\n");
        
        if (request.getUserPreferences() != null) {
            prompt.append("User preferences:\n");
            if (request.getUserPreferences().getKeywordsRequiringAttention() != null) {
                prompt.append("- Keywords requiring attention: ").append(request.getUserPreferences().getKeywordsRequiringAttention()).append("\n");
            }
            if (request.getUserPreferences().getResponseStyle() != null) {
                prompt.append("- Response style: ").append(request.getUserPreferences().getResponseStyle()).append("\n");
            }
        }
        
        prompt.append("\nRespond in JSON format with fields: requiresPersonalAttention, confidenceScore, reasonForDecision, generatedResponse, category, sentiment\n");
        
        return prompt.toString();
    }
    
    private String buildResponsePrompt(EmailAnalysisRequest request) {
        StringBuilder prompt = new StringBuilder();
        prompt.append("You are generating a professional email response. ");
        
        if (request.getUserPreferences() != null && request.getUserPreferences().getResponseStyle() != null) {
            prompt.append("Use a ").append(request.getUserPreferences().getResponseStyle()).append(" tone. ");
        }
        
        if (request.getHistoricalResponses() != null && !request.getHistoricalResponses().isEmpty()) {
            prompt.append("Consider these historical response patterns:\n");
            request.getHistoricalResponses().forEach(response -> 
                prompt.append("- ").append(response).append("\n"));
        }
        
        prompt.append("Generate a concise, helpful response that addresses the sender's needs.");
        
        return prompt.toString();
    }
    
    private String formatEmailForAnalysis(EmailAnalysisRequest request) {
        return String.format(
                "Subject: %s\nFrom: %s <%s>\nReceived: %s\n\nContent:\n%s",
                request.getSubject(),
                request.getSenderName(),
                request.getSenderEmail(),
                request.getReceivedTime(),
                request.getContent()
        );
    }
    
    private String formatEmailForResponse(EmailAnalysisRequest request) {
        return formatEmailForAnalysis(request);
    }
    
    private EmailAnalysisResponse parseAnalysisResponse(String response) {
        try {
            // Extract the JSON content from the OpenAI response
            String jsonContent = extractContentFromResponse(response);
            return objectMapper.readValue(jsonContent, EmailAnalysisResponse.class);
        } catch (Exception e) {
            logger.error("Error parsing OpenAI analysis response", e);
            // Return a default response
            return new EmailAnalysisResponse(true, 0.5, "Unable to analyze email", "");
        }
    }
    
    private String extractContentFromResponse(String response) {
        try {
            Map<String, Object> responseMap = objectMapper.readValue(response, Map.class);
            List<Map<String, Object>> choices = (List<Map<String, Object>>) responseMap.get("choices");
            if (choices != null && !choices.isEmpty()) {
                Map<String, Object> message = (Map<String, Object>) choices.get(0).get("message");
                return (String) message.get("content");
            }
        } catch (Exception e) {
            logger.error("Error extracting content from OpenAI response", e);
        }
        return response; // Fallback to original response
    }
    
    // Internal classes for OpenAI API
    private static class OpenAIRequest {
        public String model;
        public List<Message> messages;
        @JsonProperty("max_tokens")
        public int maxTokens;
        public double temperature;
    }
    
    private static class Message {
        public String role;
        public String content;
        
        public Message(String role, String content) {
            this.role = role;
            this.content = content;
        }
    }
}
