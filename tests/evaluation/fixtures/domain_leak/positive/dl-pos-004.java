import org.springframework.web.bind.annotation.*;
@RequestMapping("/api")
class ApiController {
    @GetMapping("/items")
    public ItemEntity getItem() { return null; }
}
