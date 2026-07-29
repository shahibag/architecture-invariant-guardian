import org.springframework.scheduling.annotation.Scheduled;
class CronMonitor {
    @Scheduled(cron = "*/30 * * * * *")
    public void checkAndPersist() {
        var data = fetchData();
        repository.persist(data);
    }
}
