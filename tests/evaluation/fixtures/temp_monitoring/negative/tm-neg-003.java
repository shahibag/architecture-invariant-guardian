class BatchProcessor {
    void process() {
        for (int i = 0; i < items.size(); i++) {
            save(items.get(i));
        }
    }
}
