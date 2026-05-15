package com.intelligentassistant.emailassistant;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class IntelligentEmailAssistantApplication {

    public static void main(String[] args) {
        SpringApplication.run(IntelligentEmailAssistantApplication.class, args);
    }
}
