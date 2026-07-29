class Waiter {
    void pause() throws InterruptedException {
        Thread.sleep(100);
        log.info("Paused");
    }
}
