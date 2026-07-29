import org.springframework.scheduling.annotation.Scheduled;
class OrderService {
    @Scheduled(fixedDelay = 5000)
    public void retryOrders() {
        orderRepository.save(order);
    }
}
