package com.ats;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * ATS Backend Application - Java 21 / Spring Boot 3
 * Migrated from Python FastAPI to enterprise-grade Java.
 */
@SpringBootApplication
@EnableAsync
@EnableScheduling
public class AtsBackendApplication {

    public static void main(String[] args) {
        SpringApplication.run(AtsBackendApplication.class, args);
    }
}
