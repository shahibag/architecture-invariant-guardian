import java.util.concurrent.*;
class PollingService {
    void start() {
        ScheduledExecutorService executor = Executors.newScheduledThreadPool(1);
        executor.scheduleAtFixedRate(() -> {
            checkAndUpdate();
            repository.save(state);
        }, 0, 10, TimeUnit.SECONDS);
    }
}
