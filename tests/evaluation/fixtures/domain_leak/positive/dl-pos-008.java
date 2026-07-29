import jakarta.persistence.Entity;
import org.springframework.web.bind.annotation.*;
@Entity
class UserEntity {}
class Outer {
    @RestController
    class InnerController {
        @GetMapping("/nested")
        public UserEntity getNested() { return null; }
    }
}
