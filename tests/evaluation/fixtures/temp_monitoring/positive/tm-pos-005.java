class InfinitePoller {
    void run() {
        for (;;) {
            if (checkQueue()) {
                transition(newState);
            }
        }
    }
}
