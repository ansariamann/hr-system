package com.ats.exception;

import lombok.Getter;
import org.springframework.http.HttpStatus;

/**
 * Base application exception that carries an HTTP status.
 */
@Getter
public class AtsException extends RuntimeException {

    private final HttpStatus status;

    public AtsException(String message, HttpStatus status) {
        super(message);
        this.status = status;
    }

    public AtsException(String message, HttpStatus status, Throwable cause) {
        super(message, cause);
        this.status = status;
    }
}
