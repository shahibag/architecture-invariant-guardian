import org.springframework.web.bind.annotation.*;
@RestController
class OrderController {
    @GetMapping("/orders")
    public OrderResponse getOrder() { return null; }
}
