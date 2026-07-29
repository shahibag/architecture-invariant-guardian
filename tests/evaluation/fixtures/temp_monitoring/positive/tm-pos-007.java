import java.util.concurrent.TimeUnit;
class BackoffRetry {
    void retry() {
        for (int attempt = 0; attempt < 3; attempt++) {
            try {
                publishEvent(order);
                break;
            } catch (Exception e) {
                TimeUnit.MILLISECONDS.sleep(500);
            }
        }
    }
}
