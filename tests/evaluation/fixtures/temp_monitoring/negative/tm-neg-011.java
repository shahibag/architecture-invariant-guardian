import org.springframework.scheduling.annotation.Scheduled;
class OldScheduler {
    @Scheduled(fixedDelay = 5000)
    public void oldMethod() { save(); }
}
