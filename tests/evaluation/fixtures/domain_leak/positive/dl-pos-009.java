import jakarta.persistence.Embeddable;
import org.springframework.web.bind.annotation.*;
@Embeddable
class Address {}
@RestController
class AddressController {
    @GetMapping("/address")
    public Address getAddress() { return null; }
}
