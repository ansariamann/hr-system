package com.ats.exception;

import org.springframework.http.HttpStatus;

public class BusinessRuleException extends AtsException {
    public BusinessRuleException(String message) {
        super(message, HttpStatus.UNPROCESSABLE_ENTITY);
    }
}
