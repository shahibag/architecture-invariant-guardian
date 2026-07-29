import org.springframework.web.bind.annotation.*;
@RestController
class CounterController {
    @GetMapping("/count")
    public int getCount() { return 42; }
}
