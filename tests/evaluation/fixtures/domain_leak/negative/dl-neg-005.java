import org.springframework.web.bind.annotation.*;
@RestController
class OrderController {
    @GetMapping("/orders")
    public OrderDTO getOrder() { return null; }
}
