class ResilientClient {
    void call() {
        for (int i = 0; i < 3; i++) {
            try {
                httpClient.execute(request);
                break;
            } catch (IOException e) {
                Thread.sleep((long) Math.pow(2, i) * 100);
            }
        }
    }
}
