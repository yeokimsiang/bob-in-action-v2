package com.ingramtrials.base;

import java.util.Map;
import javax.servlet.http.HttpServletRequest;
import org.springframework.boot.web.servlet.error.ErrorController;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class FallbackError implements ErrorController {
    @RequestMapping("/error")
    public ResponseEntity<Map<String,Object>> error(HttpServletRequest request) {
        Object code=request.getAttribute("javax.servlet.error.status_code");
        int status=code instanceof Integer ? (Integer)code : 500;
        HttpStatus http=HttpStatus.resolve(status);
        if (http==null) http=HttpStatus.INTERNAL_SERVER_ERROR;
        return ResponseEntity.status(http).body(Desk.map("error",http.name(),"message",http.getReasonPhrase()));
    }
}
