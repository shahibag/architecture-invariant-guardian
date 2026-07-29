import org.springframework.scheduling.annotation.Scheduled;
class EventMonitor {
    @Scheduled(
        fixedRate = 10000,
        initialDelay = 5000
    )
    public void emitPending() {
        eventBus.emit(pendingEvents);
    }
}
