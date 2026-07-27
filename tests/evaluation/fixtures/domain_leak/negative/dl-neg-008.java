import org.springframework.web.bind.annotation.*;
@RestController
class OrderController {
    @GetMapping("/orders")
    public OrderService getService() { return null; }
}
