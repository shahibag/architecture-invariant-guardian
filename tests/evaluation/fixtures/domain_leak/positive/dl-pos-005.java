import jakarta.persistence.MappedSuperclass;
import org.springframework.web.bind.annotation.*;
@MappedSuperclass
class BaseEntity {}
@RestController
class UserController {
    @GetMapping("/user")
    public BaseEntity getUser() { return null; }
}
