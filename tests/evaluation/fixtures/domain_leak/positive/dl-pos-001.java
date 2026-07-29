import jakarta.persistence.Entity;
import org.springframework.web.bind.annotation.*;
@Entity
class OrderEntity {}
@RestController
class OrderController {
    @GetMapping("/orders")
    public OrderEntity getOrder() { return null; }
}
