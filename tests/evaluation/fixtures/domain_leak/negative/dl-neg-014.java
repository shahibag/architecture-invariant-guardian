import org.springframework.web.bind.annotation.*;
@RestController
class RecordPatternController {
    @GetMapping("/shape")
    public String describe(Object shape) {
        record Point(int x, int y) {}
        if (shape instanceof Point(var x, var y)) {
            return x + "," + y;
        }
        return "unknown";
    }
}
