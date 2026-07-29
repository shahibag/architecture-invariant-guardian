import jakarta.persistence.Entity;
import org.springframework.web.bind.annotation.*;
@Entity
class OrderAggregate {}
@RestController
class ComplexController {
    @GetMapping("/complex")
    public OrderAggregate
        getComplexOrder(
            @RequestParam String id)
            throws Exception {
        return null;
    }
}
