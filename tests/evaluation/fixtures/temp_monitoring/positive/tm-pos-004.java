class OrderPoller {
    void poll() {
        while (true) {
            checkStatus();
            orderRepository.update(order);
        }
    }
}
