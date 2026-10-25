# Multi-stage Dockerfile for ATS Java Backend (Spring Boot 3 / Java 21)
# Stage 1: Build
FROM maven:3.9-eclipse-temurin-21 AS builder

WORKDIR /build

# Cache dependencies
COPY pom.xml .
RUN mvn dependency:go-offline -B

# Copy source code and build package
COPY src ./src
RUN mvn clean package -DskipTests -B

# Stage 2: Production Runtime
FROM eclipse-temurin:21-jre-jammy AS runtime

# Install system dependencies including Tesseract OCR for Tess4J fallback
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create upload and log directories
RUN mkdir -p /app/uploads /app/logs

# Copy executable jar from builder stage
COPY --from=builder /build/target/ats-backend-*.jar app.jar

# Expose Spring Boot API port (8080) and JobRunr dashboard (8000)
EXPOSE 8080 8000

# Health check using Spring Boot Actuator
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/actuator/health || exit 1

# Launch with JVM optimizations for containerized environments
ENTRYPOINT ["java", \
    "-XX:+UseContainerSupport", \
    "-XX:MaxRAMPercentage=75.0", \
    "-Djava.security.egd=file:/dev/./urandom", \
    "-jar", "app.jar"]
