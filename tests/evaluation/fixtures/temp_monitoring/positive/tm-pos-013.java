package com.example;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
class DataPoller {
    @Scheduled(fixedDelay=5000)
    public void poll() {
        repository.save(new Record());
    }
}
