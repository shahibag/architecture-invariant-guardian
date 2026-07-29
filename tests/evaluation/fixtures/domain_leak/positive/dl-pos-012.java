import org.springframework.web.bind.annotation.*;
@RestController
class ConfigController {
    @PutMapping("/config")
    public ConfigPersistenceModel update(@RequestBody ConfigPersistenceModel m) { return m; }
}
