import org.springframework.web.bind.annotation.*;
@RestController
class EventController {
    @PostMapping("/events")
    public OrderCreatedEvent publish(@RequestBody OrderCreatedEvent e) { return e; }
}
