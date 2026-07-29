class StatusRetry {
    void waitForStatus() {
        while (!ready) {
            try {
                Thread.sleep(2000);
                setStatus(Status.READY);
            } catch (InterruptedException e) {
                break;
            }
        }
    }
}
