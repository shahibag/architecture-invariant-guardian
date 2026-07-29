import java.util.concurrent.*;
class AsyncWorker {
    void work() {
        executor.submit(() -> doWork());
    }
}
