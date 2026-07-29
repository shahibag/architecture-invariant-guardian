import java.util.concurrent.*;
class OrderService {
    void init() {
        ScheduledExecutorService executor = Executors.newScheduledThreadPool(1);
        executor.schedule(() -> retryWork(), 30, TimeUnit.SECONDS);
    }
}
