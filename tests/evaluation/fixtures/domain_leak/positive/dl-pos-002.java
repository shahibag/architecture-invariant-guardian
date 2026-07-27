import jakarta.persistence.Entity;
import java.util.List;
import org.springframework.web.bind.annotation.*;
@Entity
class OrderEntity {}
@RestController
class OrderController {
    @GetMapping("/orders")
    public List<OrderEntity> getOrders() { return null; }
}
