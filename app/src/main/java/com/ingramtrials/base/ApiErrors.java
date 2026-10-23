package com.ingramtrials.base;

import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.server.ResponseStatusException;

@ControllerAdvice
public class ApiErrors {
    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<Map<String,Object>> expected(ResponseStatusException ex) {
        return ResponseEntity.status(ex.getStatus()).body(Desk.map("error",ex.getStatus().name(),"message",ex.getReason()));
    }
    @ExceptionHandler({HttpMessageNotReadableException.class,MissingServletRequestParameterException.class,MethodArgumentTypeMismatchException.class})
    public ResponseEntity<Map<String,Object>> badRequest(Exception ex) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Desk.map("error","BAD_REQUEST","message","Invalid request input"));
    }
    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    public ResponseEntity<Map<String,Object>> wrongMethod(Exception ex) {
        return ResponseEntity.status(HttpStatus.METHOD_NOT_ALLOWED).body(Desk.map("error","METHOD_NOT_ALLOWED","message","Method not allowed"));
    }
    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String,Object>> unexpected(Exception ex) {
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(Desk.map("error","INTERNAL_SERVER_ERROR","message",ex.getMessage()));
    }
}
