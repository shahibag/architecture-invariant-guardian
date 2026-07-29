import org.springframework.web.bind.annotation.*;
@RestController
class OrderController {
    @PostMapping("/orders")
    public void create(@RequestBody CreateRequest req) {}
}
