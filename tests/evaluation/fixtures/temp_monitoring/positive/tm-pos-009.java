import java.util.concurrent.*;
class CacheFlusher {
    void init() {
        ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(1);
        scheduler.scheduleWithFixedDelay(
            () -> cache.flush(), 1, 5, TimeUnit.MINUTES);
    }
}
