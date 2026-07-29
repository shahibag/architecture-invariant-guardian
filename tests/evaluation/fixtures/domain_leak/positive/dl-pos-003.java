import jakarta.persistence.Entity;
import org.springframework.web.bind.annotation.*;
@Entity
class OrderEntity {}
@RestController
class OrderController {
    @PostMapping("/orders")
    public void create(@RequestBody OrderEntity req) {}
}
