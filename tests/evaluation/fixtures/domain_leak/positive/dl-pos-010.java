import org.springframework.web.bind.annotation.*;
@RestController
class ProductController {
    @GetMapping("/product")
    public ProductEntity getProduct() { return null; }
}
