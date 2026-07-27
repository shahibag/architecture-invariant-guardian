package com.example;

import jakarta.persistence.Entity;
import org.springframework.web.bind.annotation.*;

@Entity
class ReportEntity {
    private Long id;
}

@RestController
class ReportController {
    @GetMapping("/report")
    public ReportEntity generateReport() { return null; }
}
