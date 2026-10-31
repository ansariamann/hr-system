# Multi-stage Dockerfile for ATS Java Backend (Spring Boot 3 / Java 21)

# ── Stage 1: Build ─────────────────────────────────────────────────────────
FROM maven:3.9-eclipse-temurin-21 AS builder

WORKDIR /build

# Cache dependencies first (layer cache-friendly)
COPY pom.xml .
RUN mvn dependency:go-offline -B

# Copy source and build
COPY src ./src
RUN mvn clean package -DskipTests -B

# ── Stage 2: Production Runtime ────────────────────────────────────────────
FROM eclipse-temurin:21-jre-jammy AS runtime

# Install system dependencies including Tesseract OCR for Tess4J fallback
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user to run the application (security hardening)
RUN groupadd --system atsapp && useradd --system --gid atsapp --no-create-home atsapp

WORKDIR /app

# Create upload and log directories, owned by the app user
RUN mkdir -p /app/uploads /app/logs \
    && chown -R atsapp:atsapp /app

# Copy executable jar from builder stage
COPY --from=builder --chown=atsapp:atsapp /build/target/ats-backend-*.jar app.jar

# Switch to non-root user
USER atsapp

# Expose only the API port; JobRunr dashboard (8000) is NOT exposed to the host
EXPOSE 8080

# Health check via Spring Boot Actuator
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/actuator/health || exit 1

# Launch with JVM optimizations for containerised environments
ENTRYPOINT ["java", \
    "-XX:+UseContainerSupport", \
    "-XX:MaxRAMPercentage=75.0", \
    "-Djava.security.egd=file:/dev/./urandom", \
    "-jar", "app.jar"]
