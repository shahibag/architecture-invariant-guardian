import org.springframework.web.bind.annotation.*;
@RestController
class OrderController {
    @GetMapping("/orders")
    public OrderRecord getOrder() { return null; }
}
record OrderRecord(String id, int total) {}
