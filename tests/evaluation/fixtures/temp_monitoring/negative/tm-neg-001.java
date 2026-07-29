import org.springframework.scheduling.annotation.Scheduled;
class DailyReconciliation {
    /** Daily batch reconciliation — source of truth for balances. */
    @Scheduled(cron = "0 0 2 * * *")
    public void reconcile() {
        report.generate();
    }
}
