import org.springframework.web.bind.annotation.*;
@RestController
class OrderController {
    @GetMapping("/orders")
    public String getOrder() { return "ok"; }
}
