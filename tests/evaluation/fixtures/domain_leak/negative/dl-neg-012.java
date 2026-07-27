import org.springframework.web.bind.annotation.*;
// @RestController
// public OrderEntity getOrder() {}
@RestController
class CommentController {
    @GetMapping("/comment")
    public OrderResponse safeMethod() { return null; }
}
