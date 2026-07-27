class RetryService {
    void process() {
        for (int i = 0; i < 5; i++) {
            try {
                doWork();
                repository.save(result);
                break;
            } catch (Exception e) {
                Thread.sleep(1000);
            }
        }
    }
}
