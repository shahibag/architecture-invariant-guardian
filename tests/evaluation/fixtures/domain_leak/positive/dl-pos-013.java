import jakarta.persistence.Entity;
import org.springframework.web.bind.annotation.*;
@Entity
class PaymentEntity {}
@RestController
class PaymentController {
    @GetMapping("/payments")
    public PaymentEntity getPayment() { return null; }
}
