import jakarta.persistence.Entity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.*;
@Entity
class OrderPersistenceModel {}
@Controller
class LegacyController {
    @GetMapping("/legacy")
    @ResponseBody
    public OrderPersistenceModel getLegacy() { return null; }
}
