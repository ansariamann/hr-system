package com.ats.api.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Builder;
import lombok.Data;

import java.time.Instant;
import java.util.UUID;

/** Auth token response — matches FastAPI Token schema. */
@Data
@Builder
public class TokenResponse {

    @JsonProperty("access_token")
    private String accessToken;

    @JsonProperty("token_type")
    @Builder.Default
    private String tokenType = "bearer";

    @JsonProperty("expires_in")
    private long expiresIn;

    @JsonProperty("user_id")
    private UUID userId;

    @JsonProperty("client_id")
    private UUID clientId;

    private String email;

    @JsonProperty("full_name")
    private String fullName;

    private String role;
}
