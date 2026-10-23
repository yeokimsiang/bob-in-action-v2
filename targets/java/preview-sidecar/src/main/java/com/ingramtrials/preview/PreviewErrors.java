package com.ingramtrials.preview;

import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.server.ResponseStatusException;

@ControllerAdvice
public class PreviewErrors {

    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<Map<String,Object>> expected(ResponseStatusException ex) {
        return ResponseEntity.status(ex.getStatusCode())
            .body(PreviewController.map("error", ex.getStatusCode().toString(), "message", ex.getReason()));
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<Map<String,Object>> badRequest(Exception ex) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
            .body(PreviewController.map("error", "BAD_REQUEST", "message", "Invalid request input"));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String,Object>> unexpected(Exception ex) {
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
            .body(PreviewController.map("error", "INTERNAL_SERVER_ERROR", "message", "An unexpected error occurred"));
    }
}
