package com.ats.sse;

import com.ats.domain.entity.User;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * Server-Sent Events (SSE) controller.
 * Replaces Python FastAPI SSE endpoints (sse.py).
 *
 * - Clients subscribe with their JWT token.
 * - Events are broadcast to all emitters for a given client_id.
 * - Heartbeat pings are sent every 15 seconds to prevent client timeout disconnects.
 */
@Slf4j
@Tag(name = "Real-time Updates", description = "Server-Sent Events for live notifications")
@RestController
@RequestMapping("/api/v1/sse")
public class SseController {

    // client_id -> emitter map (supports multiple browser tabs per tenant)
    private final Map<String, SseEmitter> emitters = new ConcurrentHashMap<>();

    // Heartbeat executor — 15s pings to prevent connection timeout
    private final ScheduledExecutorService heartbeatExecutor = Executors.newSingleThreadScheduledExecutor();

    public SseController() {
        // Send heartbeat every 15 seconds to all connected clients
        heartbeatExecutor.scheduleAtFixedRate(this::sendHeartbeats, 15, 15, TimeUnit.SECONDS);
    }

    /**
     * Subscribe to real-time updates for the authenticated tenant.
     */
    @Operation(summary = "Subscribe to real-time SSE events")
    @GetMapping(value = "/subscribe", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter subscribe(@AuthenticationPrincipal User user) {
        String key = user.getClientId().toString() + ":" + user.getId().toString();
        SseEmitter emitter = new SseEmitter(Long.MAX_VALUE);

        emitter.onCompletion(() -> {
            emitters.remove(key);
            log.debug("SSE client disconnected: {}", key);
        });
        emitter.onTimeout(() -> {
            emitters.remove(key);
            log.debug("SSE client timed out: {}", key);
        });
        emitter.onError(e -> {
            emitters.remove(key);
            log.debug("SSE client error for {}: {}", key, e.getMessage());
        });

        emitters.put(key, emitter);
        log.debug("SSE client connected: {} (total: {})", key, emitters.size());

        // Send initial connected event
        try {
            emitter.send(SseEmitter.event()
                    .name("connected")
                    .data(Map.of("status", "connected", "client_id", user.getClientId())));
        } catch (IOException e) {
            emitters.remove(key);
        }

        return emitter;
    }

    /**
     * Broadcast an event to all subscribers of a given client (tenant).
     * Called internally from services (e.g., ApplicationService after HIRED transition).
     */
    public void broadcastToClient(UUID clientId, String eventName, Object data) {
        String prefix = clientId.toString() + ":";
        emitters.entrySet().stream()
                .filter(e -> e.getKey().startsWith(prefix))
                .forEach(entry -> {
                    try {
                        entry.getValue().send(SseEmitter.event().name(eventName).data(data));
                    } catch (IOException ex) {
                        emitters.remove(entry.getKey());
                    }
                });
    }

    private void sendHeartbeats() {
        emitters.forEach((key, emitter) -> {
            try {
                emitter.send(SseEmitter.event().comment("heartbeat"));
            } catch (IOException e) {
                emitters.remove(key);
            }
        });
    }
}
