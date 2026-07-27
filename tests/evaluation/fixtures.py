"""Evaluation corpus fixtures for v0.2 — 48 cases covering both invariants.

Each case is a dict with:
- id: stable case ID
- invariant_id: "no-domain-leak" or "no-temporary-monitoring"
- expected_decision: "confirm" or "reject"
- description: human-readable rationale
- source: Java source string
- file_path: repository-relative path
- changed_lines: set of line numbers that are "changed"
- syntax_features: list of Java features exercised
- expected_evidence_location: expected start_line
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Domain-leak — 12 positive cases (should detect a leak)
# ---------------------------------------------------------------------------

DOMAIN_LEAK_POSITIVE = [
    {
        "id": "dl-pos-001",
        "invariant_id": "no-domain-leak",
        "expected_decision": "confirm",
        "description": "RestController returns @Entity-annotated class",
        "source": (
            "import jakarta.persistence.Entity;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@Entity\n"
            "class OrderEntity {}\n"
            "@RestController\n"
            "class OrderController {\n"
            "    @GetMapping(\"/orders\")\n"
            "    public OrderEntity getOrder() { return null; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/OrderController.java",
        "changed_lines": {8},
        "syntax_features": ["annotations"],
        "expected_evidence_location": 8,
    },
    {
        "id": "dl-pos-002",
        "invariant_id": "no-domain-leak",
        "expected_decision": "confirm",
        "description": "Controller returns List of @Entity type",
        "source": (
            "import jakarta.persistence.Entity;\n"
            "import java.util.List;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@Entity\n"
            "class OrderEntity {}\n"
            "@RestController\n"
            "class OrderController {\n"
            "    @GetMapping(\"/orders\")\n"
            "    public List<OrderEntity> getOrders() { return null; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/OrderController.java",
        "changed_lines": {9},
        "syntax_features": ["generics", "annotations"],
        "expected_evidence_location": 9,
    },
    {
        "id": "dl-pos-003",
        "invariant_id": "no-domain-leak",
        "expected_decision": "confirm",
        "description": "Controller accepts @Entity type as @RequestBody",
        "source": (
            "import jakarta.persistence.Entity;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@Entity\n"
            "class OrderEntity {}\n"
            "@RestController\n"
            "class OrderController {\n"
            "    @PostMapping(\"/orders\")\n"
            "    public void create(@RequestBody OrderEntity req) {}\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/OrderController.java",
        "changed_lines": {8},
        "syntax_features": ["annotations"],
        "expected_evidence_location": 8,
    },
    {
        "id": "dl-pos-004",
        "invariant_id": "no-domain-leak",
        "expected_decision": "confirm",
        "description": "@RequestMapping controller returns Entity-named type",
        "source": (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RequestMapping(\"/api\")\n"
            "class ApiController {\n"
            "    @GetMapping(\"/items\")\n"
            "    public ItemEntity getItem() { return null; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/ApiController.java",
        "changed_lines": {5},
        "syntax_features": ["annotations"],
        "expected_evidence_location": 5,
    },
    {
        "id": "dl-pos-005",
        "invariant_id": "no-domain-leak",
        "expected_decision": "confirm",
        "description": "Controller returns @MappedSuperclass type",
        "source": (
            "import jakarta.persistence.MappedSuperclass;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@MappedSuperclass\n"
            "class BaseEntity {}\n"
            "@RestController\n"
            "class UserController {\n"
            "    @GetMapping(\"/user\")\n"
            "    public BaseEntity getUser() { return null; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/UserController.java",
        "changed_lines": {8},
        "syntax_features": ["annotations"],
        "expected_evidence_location": 8,
    },
    {
        "id": "dl-pos-006",
        "invariant_id": "no-domain-leak",
        "expected_decision": "confirm",
        "description": "@Controller with @ResponseBody returns persistence type",
        "source": (
            "import jakarta.persistence.Entity;\n"
            "import org.springframework.stereotype.Controller;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@Entity\n"
            "class OrderPersistenceModel {}\n"
            "@Controller\n"
            "class LegacyController {\n"
            "    @GetMapping(\"/legacy\")\n"
            "    @ResponseBody\n"
            "    public OrderPersistenceModel getLegacy() { return null; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/LegacyController.java",
        "changed_lines": {10},
        "syntax_features": ["annotations"],
        "expected_evidence_location": 10,
    },
    {
        "id": "dl-pos-007",
        "invariant_id": "no-domain-leak",
        "expected_decision": "confirm",
        "description": "Multiline method signature returns entity type",
        "source": (
            "import jakarta.persistence.Entity;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@Entity\n"
            "class OrderAggregate {}\n"
            "@RestController\n"
            "class ComplexController {\n"
            "    @GetMapping(\"/complex\")\n"
            "    public OrderAggregate\n"
            "        getComplexOrder(\n"
            "            @RequestParam String id)\n"
            "            throws Exception {\n"
            "        return null;\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/ComplexController.java",
        "changed_lines": {9},
        "syntax_features": ["multiline_method_declaration", "annotations"],
        "expected_evidence_location": 9,
    },
    {
        "id": "dl-pos-008",
        "invariant_id": "no-domain-leak",
        "expected_decision": "confirm",
        "description": "Nested controller class leaks entity",
        "source": (
            "import jakarta.persistence.Entity;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@Entity\n"
            "class UserEntity {}\n"
            "class Outer {\n"
            "    @RestController\n"
            "    class InnerController {\n"
            "        @GetMapping(\"/nested\")\n"
            "        public UserEntity getNested() { return null; }\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/NestedController.java",
        "changed_lines": {9},
        "syntax_features": ["nested_classes", "annotations"],
        "expected_evidence_location": 9,
    },
    {
        "id": "dl-pos-009",
        "invariant_id": "no-domain-leak",
        "expected_decision": "confirm",
        "description": "@Embeddable type exposed in controller",
        "source": (
            "import jakarta.persistence.Embeddable;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@Embeddable\n"
            "class Address {}\n"
            "@RestController\n"
            "class AddressController {\n"
            "    @GetMapping(\"/address\")\n"
            "    public Address getAddress() { return null; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/AddressController.java",
        "changed_lines": {8},
        "syntax_features": ["annotations"],
        "expected_evidence_location": 8,
    },
    {
        "id": "dl-pos-010",
        "invariant_id": "no-domain-leak",
        "expected_decision": "confirm",
        "description": "Naming convention Entity without annotation still detected",
        "source": (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class ProductController {\n"
            "    @GetMapping(\"/product\")\n"
            "    public ProductEntity getProduct() { return null; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/ProductController.java",
        "changed_lines": {5},
        "syntax_features": ["annotations"],
        "expected_evidence_location": 5,
    },
    {
        "id": "dl-pos-011",
        "invariant_id": "no-domain-leak",
        "expected_decision": "confirm",
        "description": "Aggregate suffix naming convention exposed",
        "source": (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class CartController {\n"
            "    @GetMapping(\"/cart\")\n"
            "    public ShoppingCartAggregate getCart() { return null; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/CartController.java",
        "changed_lines": {5},
        "syntax_features": ["annotations"],
        "expected_evidence_location": 5,
    },
    {
        "id": "dl-pos-012",
        "invariant_id": "no-domain-leak",
        "expected_decision": "confirm",
        "description": "PersistenceModel naming convention exposed in @PutMapping",
        "source": (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class ConfigController {\n"
            "    @PutMapping(\"/config\")\n"
            "    public ConfigPersistenceModel update(@RequestBody ConfigPersistenceModel m) { return m; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/ConfigController.java",
        "changed_lines": {5},
        "syntax_features": ["annotations"],
        "expected_evidence_location": 5,
    },
]

# ---------------------------------------------------------------------------
# Domain-leak — 12 negative/allowed cases (should NOT detect a leak)
# ---------------------------------------------------------------------------

DOMAIN_LEAK_NEGATIVE = [
    {
        "id": "dl-neg-001",
        "invariant_id": "no-domain-leak",
        "expected_decision": "reject",
        "description": "DTO return type — safe",
        "source": (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class OrderController {\n"
            "    @GetMapping(\"/orders\")\n"
            "    public OrderResponse getOrder() { return null; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/OrderController.java",
        "changed_lines": {5},
        "syntax_features": ["annotations"],
        "expected_evidence_location": None,
    },
    {
        "id": "dl-neg-002",
        "invariant_id": "no-domain-leak",
        "expected_decision": "reject",
        "description": "Java record used as response — safe",
        "source": (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class OrderController {\n"
            "    @GetMapping(\"/orders\")\n"
            "    public OrderRecord getOrder() { return null; }\n"
            "}\n"
            "record OrderRecord(String id, int total) {}\n"
        ),
        "file_path": "src/main/java/com/example/OrderController.java",
        "changed_lines": {5},
        "syntax_features": ["annotations", "records"],
        "expected_evidence_location": None,
    },
    {
        "id": "dl-neg-003",
        "invariant_id": "no-domain-leak",
        "expected_decision": "reject",
        "description": "Non-controller public method — not a leak",
        "source": (
            "class OrderService {\n"
            "    public OrderEntity getOrder() { return null; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/OrderService.java",
        "changed_lines": {2},
        "syntax_features": [],
        "expected_evidence_location": None,
    },
    {
        "id": "dl-neg-004",
        "invariant_id": "no-domain-leak",
        "expected_decision": "reject",
        "description": "No matching internal type — clean",
        "source": (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class OrderController {\n"
            "    @GetMapping(\"/orders\")\n"
            "    public String getOrder() { return \"ok\"; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/OrderController.java",
        "changed_lines": {5},
        "syntax_features": ["annotations"],
        "expected_evidence_location": None,
    },
    {
        "id": "dl-neg-005",
        "invariant_id": "no-domain-leak",
        "expected_decision": "reject",
        "description": "Naming convention DTO — not Entity/Aggregate/PersistenceModel",
        "source": (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class OrderController {\n"
            "    @GetMapping(\"/orders\")\n"
            "    public OrderDTO getOrder() { return null; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/OrderController.java",
        "changed_lines": {5},
        "syntax_features": ["annotations"],
        "expected_evidence_location": None,
    },
    {
        "id": "dl-neg-006",
        "invariant_id": "no-domain-leak",
        "expected_decision": "reject",
        "description": "Naming convention Response — safe",
        "source": (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class OrderController {\n"
            "    @GetMapping(\"/orders\")\n"
            "    public OrderResponse getOrder() { return null; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/OrderController.java",
        "changed_lines": {5},
        "syntax_features": ["annotations"],
        "expected_evidence_location": None,
    },
    {
        "id": "dl-neg-007",
        "invariant_id": "no-domain-leak",
        "expected_decision": "reject",
        "description": "Public event class used in controller — explicitly public contract",
        "source": (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class EventController {\n"
            "    @PostMapping(\"/events\")\n"
            "    public OrderCreatedEvent publish(@RequestBody OrderCreatedEvent e) { return e; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/EventController.java",
        "changed_lines": {5},
        "syntax_features": ["annotations"],
        "expected_evidence_location": None,
    },
    {
        "id": "dl-neg-008",
        "invariant_id": "no-domain-leak",
        "expected_decision": "reject",
        "description": "Interface return type — not a concrete entity",
        "source": (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class OrderController {\n"
            "    @GetMapping(\"/orders\")\n"
            "    public OrderService getService() { return null; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/OrderController.java",
        "changed_lines": {5},
        "syntax_features": ["annotations"],
        "expected_evidence_location": None,
    },
    {
        "id": "dl-neg-009",
        "invariant_id": "no-domain-leak",
        "expected_decision": "reject",
        "description": "Void return — no leak",
        "source": (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class OrderController {\n"
            "    @PostMapping(\"/orders\")\n"
            "    public void create(@RequestBody CreateRequest req) {}\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/OrderController.java",
        "changed_lines": {5},
        "syntax_features": ["annotations"],
        "expected_evidence_location": None,
    },
    {
        "id": "dl-neg-010",
        "invariant_id": "no-domain-leak",
        "expected_decision": "reject",
        "description": "Primitive return type — no leak",
        "source": (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class CounterController {\n"
            "    @GetMapping(\"/count\")\n"
            "    public int getCount() { return 42; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/CounterController.java",
        "changed_lines": {5},
        "syntax_features": ["annotations"],
        "expected_evidence_location": None,
    },
    {
        "id": "dl-neg-011",
        "invariant_id": "no-domain-leak",
        "expected_decision": "reject",
        "description": "Prompt injection in string literal — must not alter detection",
        "source": (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class SafeController {\n"
            "    String fake = \"@Entity class Hack {}\";\n"
            "    @GetMapping(\"/safe\")\n"
            "    public String safe() { return \"@RestController public OrderEntity get() {}\"; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/SafeController.java",
        "changed_lines": {7},
        "syntax_features": ["annotations"],
        "expected_evidence_location": None,
    },
    {
        "id": "dl-neg-012",
        "invariant_id": "no-domain-leak",
        "expected_decision": "reject",
        "description": "Comment containing injection text — must not affect detection",
        "source": (
            "import org.springframework.web.bind.annotation.*;\n"
            "// @RestController\n"
            "// public OrderEntity getOrder() {}\n"
            "@RestController\n"
            "class CommentController {\n"
            "    @GetMapping(\"/comment\")\n"
            "    public OrderResponse safeMethod() { return null; }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/CommentController.java",
        "changed_lines": {8},
        "syntax_features": ["annotations"],
        "expected_evidence_location": None,
    },
]

# ---------------------------------------------------------------------------
# Temporary-monitoring — 12 positive cases (should detect monitoring)
# ---------------------------------------------------------------------------

TEMP_MONITORING_POSITIVE = [
    {
        "id": "tm-pos-001",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "confirm",
        "description": "@Scheduled method with state change",
        "source": (
            "import org.springframework.scheduling.annotation.Scheduled;\n"
            "class OrderService {\n"
            "    @Scheduled(fixedDelay = 5000)\n"
            "    public void retryOrders() {\n"
            "        orderRepository.save(order);\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/OrderService.java",
        "changed_lines": {3, 4},
        "syntax_features": ["annotations"],
        "expected_evidence_location": 3,
    },
    {
        "id": "tm-pos-002",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "confirm",
        "description": "ScheduledExecutorService.schedule call",
        "source": (
            "import java.util.concurrent.*;\n"
            "class OrderService {\n"
            "    void init() {\n"
            "        ScheduledExecutorService executor = Executors.newScheduledThreadPool(1);\n"
            "        executor.schedule(() -> retryWork(), 30, TimeUnit.SECONDS);\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/OrderService.java",
        "changed_lines": {5},
        "syntax_features": ["lambdas"],
        "expected_evidence_location": 5,
    },
    {
        "id": "tm-pos-003",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "confirm",
        "description": "scheduleAtFixedRate with state change",
        "source": (
            "import java.util.concurrent.*;\n"
            "class PollingService {\n"
            "    void start() {\n"
            "        executor.scheduleAtFixedRate(() -> {\n"
            "            checkAndUpdate();\n"
            "            repository.save(state);\n"
            "        }, 0, 10, TimeUnit.SECONDS);\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/PollingService.java",
        "changed_lines": {4},
        "syntax_features": ["lambdas"],
        "expected_evidence_location": 4,
    },
    {
        "id": "tm-pos-004",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "confirm",
        "description": "while(true) polling with state change",
        "source": (
            "class OrderPoller {\n"
            "    void poll() {\n"
            "        while (true) {\n"
            "            checkStatus();\n"
            "            orderRepository.update(order);\n"
            "        }\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/OrderPoller.java",
        "changed_lines": {3},
        "syntax_features": [],
        "expected_evidence_location": 3,
    },
    {
        "id": "tm-pos-005",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "confirm",
        "description": "for(;;) infinite polling with state transition",
        "source": (
            "class InfinitePoller {\n"
            "    void run() {\n"
            "        for (;;) {\n"
            "            if (checkQueue()) {\n"
            "                transition(newState);\n"
            "            }\n"
            "        }\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/InfinitePoller.java",
        "changed_lines": {3},
        "syntax_features": [],
        "expected_evidence_location": 3,
    },
    {
        "id": "tm-pos-006",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "confirm",
        "description": "Retry loop with Thread.sleep and state change",
        "source": (
            "class RetryService {\n"
            "    void process() {\n"
            "        for (int i = 0; i < 5; i++) {\n"
            "            try {\n"
            "                doWork();\n"
            "                repository.save(result);\n"
            "                break;\n"
            "            } catch (Exception e) {\n"
            "                Thread.sleep(1000);\n"
            "            }\n"
            "        }\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/RetryService.java",
        "changed_lines": {3},
        "syntax_features": [],
        "expected_evidence_location": 3,
    },
    {
        "id": "tm-pos-007",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "confirm",
        "description": "Retry loop with TimeUnit sleep and state change",
        "source": (
            "import java.util.concurrent.TimeUnit;\n"
            "class BackoffRetry {\n"
            "    void retry() {\n"
            "        for (int attempt = 0; attempt < 3; attempt++) {\n"
            "            try {\n"
            "                publishEvent(order);\n"
            "                break;\n"
            "            } catch (Exception e) {\n"
            "                TimeUnit.MILLISECONDS.sleep(500);\n"
            "            }\n"
            "        }\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/BackoffRetry.java",
        "changed_lines": {4},
        "syntax_features": [],
        "expected_evidence_location": 4,
    },
    {
        "id": "tm-pos-008",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "confirm",
        "description": "@Scheduled with cron expression and persist",
        "source": (
            "import org.springframework.scheduling.annotation.Scheduled;\n"
            "class CronMonitor {\n"
            "    @Scheduled(cron = \"*/30 * * * * *\")\n"
            "    public void checkAndPersist() {\n"
            "        var data = fetchData();\n"
            "        repository.persist(data);\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/CronMonitor.java",
        "changed_lines": {4},
        "syntax_features": ["annotations"],
        "expected_evidence_location": 4,
    },
    {
        "id": "tm-pos-009",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "confirm",
        "description": "scheduleWithFixedDelay with state flush",
        "source": (
            "import java.util.concurrent.*;\n"
            "class CacheFlusher {\n"
            "    void init() {\n"
            "        scheduler.scheduleWithFixedDelay(\n"
            "            () -> cache.flush(), 1, 5, TimeUnit.MINUTES);\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/CacheFlusher.java",
        "changed_lines": {4},
        "syntax_features": ["lambdas", "multiline_method_declaration"],
        "expected_evidence_location": 4,
    },
    {
        "id": "tm-pos-010",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "confirm",
        "description": "Thread.sleep with setStatus state change",
        "source": (
            "class StatusRetry {\n"
            "    void waitForStatus() {\n"
            "        while (!ready) {\n"
            "            try {\n"
            "                Thread.sleep(2000);\n"
            "                setStatus(Status.READY);\n"
            "            } catch (InterruptedException e) {\n"
            "                break;\n"
            "            }\n"
            "        }\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/StatusRetry.java",
        "changed_lines": {3},
        "syntax_features": [],
        "expected_evidence_location": 3,
    },
    {
        "id": "tm-pos-011",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "confirm",
        "description": "Multiline @Scheduled with fixedRate and emit",
        "source": (
            "import org.springframework.scheduling.annotation.Scheduled;\n"
            "class EventMonitor {\n"
            "    @Scheduled(\n"
            "        fixedRate = 10000,\n"
            "        initialDelay = 5000\n"
            "    )\n"
            "    public void emitPending() {\n"
            "        eventBus.emit(pendingEvents);\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/EventMonitor.java",
        "changed_lines": {7},
        "syntax_features": ["annotations", "multiline_method_declaration"],
        "expected_evidence_location": 7,
    },
    {
        "id": "tm-pos-012",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "confirm",
        "description": "Nested class with @Scheduled and state change",
        "source": (
            "import org.springframework.scheduling.annotation.Scheduled;\n"
            "class OuterService {\n"
            "    static class InnerMonitor {\n"
            "        @Scheduled(fixedDelay = 1000)\n"
            "        public void reconcile() {\n"
            "            repository.merge(data);\n"
            "        }\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/OuterService.java",
        "changed_lines": {5},
        "syntax_features": ["annotations", "nested_classes"],
        "expected_evidence_location": 5,
    },
]

# ---------------------------------------------------------------------------
# Temporary-monitoring — 12 negative/allowed cases (should NOT detect)
# ---------------------------------------------------------------------------

TEMP_MONITORING_NEGATIVE = [
    {
        "id": "tm-neg-001",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "reject",
        "description": "Documented daily reconciliation job — intentional",
        "source": (
            "import org.springframework.scheduling.annotation.Scheduled;\n"
            "class DailyReconciliation {\n"
            "    /** Daily batch reconciliation — source of truth for balances. */\n"
            "    @Scheduled(cron = \"0 0 2 * * *\")\n"
            "    public void reconcile() {\n"
            "        report.generate();\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/DailyReconciliation.java",
        "changed_lines": {4},
        "syntax_features": ["annotations"],
        "expected_evidence_location": None,
    },
    {
        "id": "tm-neg-002",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "reject",
        "description": "Bounded retry with exponential backoff — resilience pattern",
        "source": (
            "class ResilientClient {\n"
            "    void call() {\n"
            "        for (int i = 0; i < 3; i++) {\n"
            "            try {\n"
            "                httpClient.execute(request);\n"
            "                break;\n"
            "            } catch (IOException e) {\n"
            "                Thread.sleep((long) Math.pow(2, i) * 100);\n"
            "            }\n"
            "        }\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/ResilientClient.java",
        "changed_lines": {3},
        "syntax_features": [],
        "expected_evidence_location": None,
    },
    {
        "id": "tm-neg-003",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "reject",
        "description": "Bounded for loop — not infinite polling",
        "source": (
            "class BatchProcessor {\n"
            "    void process() {\n"
            "        for (int i = 0; i < items.size(); i++) {\n"
            "            save(items.get(i));\n"
            "        }\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/BatchProcessor.java",
        "changed_lines": {3},
        "syntax_features": [],
        "expected_evidence_location": None,
    },
    {
        "id": "tm-neg-004",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "reject",
        "description": "Scheduled annotation on a class without a method — no detection",
        "source": (
            "class NotAScheduler {\n"
            "    void regularWork() {\n"
            "        doStuff();\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/NotAScheduler.java",
        "changed_lines": {3},
        "syntax_features": [],
        "expected_evidence_location": None,
    },
    {
        "id": "tm-neg-005",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "reject",
        "description": "State change without monitoring — not a candidate",
        "source": (
            "class DataService {\n"
            "    void saveData(Data d) {\n"
            "        repository.save(d);\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/DataService.java",
        "changed_lines": {3},
        "syntax_features": [],
        "expected_evidence_location": None,
    },
    {
        "id": "tm-neg-006",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "reject",
        "description": "Sleep without state change or loop — not a retry pattern",
        "source": (
            "class Waiter {\n"
            "    void pause() throws InterruptedException {\n"
            "        Thread.sleep(100);\n"
            "        log.info(\"Paused\");\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/Waiter.java",
        "changed_lines": {3},
        "syntax_features": [],
        "expected_evidence_location": None,
    },
    {
        "id": "tm-neg-007",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "reject",
        "description": "Non-Java file — not evaluated",
        "source": "@Scheduled\nvoid check() { save(); }\n",
        "file_path": "src/main/kotlin/Check.kt",
        "changed_lines": {1},
        "syntax_features": [],
        "expected_evidence_location": None,
    },
    {
        "id": "tm-neg-008",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "reject",
        "description": "Prompt injection in comment — @Scheduled in a comment",
        "source": (
            "class CleanService {\n"
            "    // @Scheduled(fixedDelay = 5000)\n"
            "    // public void fakeScheduled() { save(); }\n"
            "    public void realWork() {\n"
            "        process();\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/CleanService.java",
        "changed_lines": {5},
        "syntax_features": [],
        "expected_evidence_location": None,
    },
    {
        "id": "tm-neg-009",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "reject",
        "description": "Prompt injection in string — 'while(true)' in string literal",
        "source": (
            "class SafeCode {\n"
            "    void log() {\n"
            "        String code = \"while (true) { save(); }\";\n"
            "        logger.info(code);\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/SafeCode.java",
        "changed_lines": {3},
        "syntax_features": [],
        "expected_evidence_location": None,
    },
    {
        "id": "tm-neg-010",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "reject",
        "description": "ExecutorService submit (not schedule) — not scheduling",
        "source": (
            "import java.util.concurrent.*;\n"
            "class AsyncWorker {\n"
            "    void work() {\n"
            "        executor.submit(() -> doWork());\n"
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/AsyncWorker.java",
        "changed_lines": {4},
        "syntax_features": ["lambdas"],
        "expected_evidence_location": None,
    },
    {
        "id": "tm-neg-011",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "reject",
        "description": "Unchanged file — no changed lines match method range",
        "source": (
            "import org.springframework.scheduling.annotation.Scheduled;\n"
            "class OldScheduler {\n"
            "    @Scheduled(fixedDelay = 5000)\n"
            "    public void oldMethod() { save(); }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/OldScheduler.java",
        "changed_lines": set(),  # no lines changed
        "syntax_features": ["annotations"],
        "expected_evidence_location": None,
    },
    {
        "id": "tm-neg-012",
        "invariant_id": "no-temporary-monitoring",
        "expected_decision": "reject",
        "description": "Text block containing code — must not be parsed as code",
        "source": (
            "class TextBlockUser {\n"
            "    void example() {\n"
            '        String sql = """\n'
            '            SELECT * FROM orders WHERE status = "PENDING"\n'
            '            """ ;\n'
            "    }\n"
            "}\n"
        ),
        "file_path": "src/main/java/com/example/TextBlockUser.java",
        "changed_lines": {3},
        "syntax_features": ["text_blocks"],
        "expected_evidence_location": None,
    },
]

# ---------------------------------------------------------------------------
# Combined corpus
# ---------------------------------------------------------------------------

ALL_CASES = (
    DOMAIN_LEAK_POSITIVE
    + DOMAIN_LEAK_NEGATIVE
    + TEMP_MONITORING_POSITIVE
    + TEMP_MONITORING_NEGATIVE
)
