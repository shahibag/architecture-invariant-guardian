import org.springframework.web.bind.annotation.*;
@RestController
class SafeController {
    String fake = "@Entity class Hack {}";
    @GetMapping("/safe")
    public String safe() { return "@RestController public OrderEntity get() {}"; }
}
