import org.springframework.scheduling.annotation.Scheduled;
class OuterService {
    static class InnerMonitor {
        @Scheduled(fixedDelay = 1000)
        public void reconcile() {
            repository.merge(data);
        }
    }
}
