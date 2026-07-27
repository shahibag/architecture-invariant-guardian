import org.springframework.web.bind.annotation.*;
@RestController
class CartController {
    @GetMapping("/cart")
    public ShoppingCartAggregate getCart() { return null; }
}
