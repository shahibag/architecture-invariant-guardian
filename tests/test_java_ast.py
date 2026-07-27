"""Tests for Java AST fact extraction — RED-GREEN-REFACTOR TDD.

Every production function in ``rules/java_ast.py`` must have a corresponding
failing test here before the production code is written.
"""

import pytest

# All production functions we will import after writing them.
# Sorted in dependency order so the file reads top-down as a test plan.


# ---------------------------------------------------------------------------
# RED 1: parse_java_source — basic parsing without errors
# ---------------------------------------------------------------------------
class TestParseJavaSource:
    """parse_java_source(source: str) -> tree_sitter.Tree"""

    def test_parses_valid_java_class(self) -> None:
        from invariant_guardian.rules.java_ast import parse_java_source

        tree = parse_java_source("class Foo {}")
        assert tree is not None
        # A valid parse must not have an ERROR node at the root level
        assert tree.root_node.has_error is False

    def test_parses_annotation(self) -> None:
        from invariant_guardian.rules.java_ast import parse_java_source

        tree = parse_java_source("@Deprecated class Foo {}")
        assert tree.root_node.has_error is False

    def test_parses_record(self) -> None:
        from invariant_guardian.rules.java_ast import parse_java_source

        tree = parse_java_source("record Point(int x, int y) {}")
        assert tree.root_node.has_error is False

    def test_parses_generics(self) -> None:
        from invariant_guardian.rules.java_ast import parse_java_source

        tree = parse_java_source(
            "class Box<T> { public <R> List<R> process(Supplier<R> s) { return null; } }"
        )
        assert tree.root_node.has_error is False

    def test_parses_nested_classes(self) -> None:
        from invariant_guardian.rules.java_ast import parse_java_source

        tree = parse_java_source(
            "class Outer { class Inner { class Deep {} } }"
        )
        assert tree.root_node.has_error is False

    def test_parses_multiline_method_declaration(self) -> None:
        from invariant_guardian.rules.java_ast import parse_java_source

        code = (
            "class Foo {\n"
            "    public OrderResponse\n"
            "        getOrder(String id)\n"
            "            throws IOException {\n"
            "        return null;\n"
            "    }\n"
            "}"
        )
        tree = parse_java_source(code)
        assert tree.root_node.has_error is False

    def test_parses_lambda(self) -> None:
        from invariant_guardian.rules.java_ast import parse_java_source

        tree = parse_java_source(
            "class Foo { void m() { list.stream().filter(x -> x > 1).count(); } }"
        )
        assert tree.root_node.has_error is False

    def test_parses_switch_expression(self) -> None:
        from invariant_guardian.rules.java_ast import parse_java_source

        tree = parse_java_source(
            "class Foo { int m(int x) { return switch(x) { case 1 -> 10; default -> 0; }; } }"
        )
        assert tree.root_node.has_error is False

    def test_parses_text_block(self) -> None:
        from invariant_guardian.rules.java_ast import parse_java_source

        tree = parse_java_source(
            'class Foo { String s = """\nhello\nworld\n"""; }'
        )
        assert tree.root_node.has_error is False

    def test_reports_error_for_garbage_input(self) -> None:
        from invariant_guardian.rules.java_ast import parse_java_source

        tree = parse_java_source("this is not java @@@")
        # Garbage Java should produce syntax errors
        assert tree.root_node.has_error is True


# ---------------------------------------------------------------------------
# RED 2: find_annotations — locate specific annotations on a declaration node
# ---------------------------------------------------------------------------
class TestFindAnnotations:
    """find_annotations(node, annotation_names, source) -> list[dict]"""

    def test_finds_rest_controller_on_class(self) -> None:
        from invariant_guardian.rules.java_ast import (
            find_annotations,
            parse_java_source,
        )

        source = "@RestController class Foo {}"
        tree = parse_java_source(source)
        # Find the class_declaration child
        for child in tree.root_node.children:
            if child.type == "class_declaration":
                anns = find_annotations(
                    child,
                    {"RestController"},
                    source_bytes=source.encode("utf-8"),
                )
                assert len(anns) >= 1
                assert any(a["name"] == "RestController" for a in anns)
                return
        pytest.fail("No class_declaration found")

    def test_finds_get_mapping_on_method(self) -> None:
        from invariant_guardian.rules.java_ast import (
            find_annotations,
            parse_java_source,
        )

        source = "class Foo { @GetMapping(\"/api\") void m() {} }"
        tree = parse_java_source(source)
        class_node = None
        for child in tree.root_node.children:
            if child.type == "class_declaration":
                class_node = child
                break
        assert class_node is not None
        for child in class_node.children:
            if child.type == "class_body":
                for member in child.children:
                    if member.type == "method_declaration":
                        anns = find_annotations(
                            member,
                            {"GetMapping", "PostMapping", "RequestMapping"},
                            source_bytes=source.encode("utf-8"),
                        )
                        assert len(anns) >= 1
                        assert anns[0]["name"] == "GetMapping"
                        return
        pytest.fail("No @GetMapping method found")

    def test_returns_empty_for_no_matching_annotation(self) -> None:
        from invariant_guardian.rules.java_ast import (
            find_annotations,
            parse_java_source,
        )

        source = "class Foo { void m() {} }"
        tree = parse_java_source(source)
        for child in tree.root_node.children:
            if child.type == "class_declaration":
                anns = find_annotations(
                    child, {"RestController"}, source_bytes=source.encode("utf-8")
                )
                assert anns == []
                return
        pytest.fail("No class_declaration found")

    def test_finds_entity_on_class(self) -> None:
        from invariant_guardian.rules.java_ast import (
            find_annotations,
            parse_java_source,
        )

        source = "@Entity class OrderEntity {}"
        tree = parse_java_source(source)
        for child in tree.root_node.children:
            if child.type == "class_declaration":
                anns = find_annotations(
                    child, {"Entity", "MappedSuperclass", "Embeddable"},
                    source_bytes=source.encode("utf-8"),
                )
                assert len(anns) >= 1
                assert anns[0]["name"] == "Entity"
                # Must include line number
                assert "start_line" in anns[0]
                return
        pytest.fail("No class_declaration found")


# ---------------------------------------------------------------------------
# RED 3: find_class_declarations — locate all class/interface/enum/record declarations
# ---------------------------------------------------------------------------
class TestFindClassDeclarations:
    """find_class_declarations(tree, source) -> list[dict]"""

    def test_finds_single_class(self) -> None:
        from invariant_guardian.rules.java_ast import (
            find_class_declarations,
            parse_java_source,
        )

        source = "class Foo {}"
        tree = parse_java_source(source)
        decls = find_class_declarations(tree, source.encode("utf-8"))
        assert len(decls) >= 1
        assert decls[0]["name"] == "Foo"
        assert decls[0]["kind"] == "class"

    def test_finds_record(self) -> None:
        from invariant_guardian.rules.java_ast import (
            find_class_declarations,
            parse_java_source,
        )

        source = "record Point(int x, int y) {}"
        tree = parse_java_source(source)
        decls = find_class_declarations(tree, source.encode("utf-8"))
        assert len(decls) >= 1
        assert decls[0]["name"] == "Point"
        assert decls[0]["kind"] == "record"

    def test_finds_nested_classes(self) -> None:
        from invariant_guardian.rules.java_ast import (
            find_class_declarations,
            parse_java_source,
        )

        source = "class Outer { class Inner {} }"
        tree = parse_java_source(source)
        decls = find_class_declarations(tree, source.encode("utf-8"))
        names = {d["name"] for d in decls}
        assert "Outer" in names
        assert "Inner" in names

    def test_includes_start_line(self) -> None:
        from invariant_guardian.rules.java_ast import (
            find_class_declarations,
            parse_java_source,
        )

        source = "\n\nclass Foo {}"
        tree = parse_java_source(source)
        decls = find_class_declarations(tree, source.encode("utf-8"))
        assert decls[0].get("start_line", 0) >= 3


# ---------------------------------------------------------------------------
# RED 4: find_method_declarations — locate all method declarations in a class
# ---------------------------------------------------------------------------
class TestFindMethodDeclarations:
    """find_method_declarations(class_node, source) -> list[dict]"""

    def test_finds_public_method(self) -> None:
        from invariant_guardian.rules.java_ast import (
            find_method_declarations,
            parse_java_source,
        )

        source = "class Foo { public void doWork() {} }"
        tree = parse_java_source(source)
        for child in tree.root_node.children:
            if child.type == "class_declaration":
                methods = find_method_declarations(child, source.encode("utf-8"))
                assert len(methods) == 1
                assert methods[0]["name"] == "doWork"
                assert methods[0]["return_type"] == "void"
                assert "start_line" in methods[0]
                return
        pytest.fail("No class_declaration found")

    def test_extracts_return_type(self) -> None:
        from invariant_guardian.rules.java_ast import (
            find_method_declarations,
            parse_java_source,
        )

        source = "class Foo { public OrderEntity getOrder() { return null; } }"
        tree = parse_java_source(source)
        for child in tree.root_node.children:
            if child.type == "class_declaration":
                methods = find_method_declarations(child, source.encode("utf-8"))
                assert len(methods) == 1
                assert methods[0]["return_type"] == "OrderEntity"
                return
        pytest.fail("No class_declaration found")

    def test_extracts_parameter_types(self) -> None:
        from invariant_guardian.rules.java_ast import (
            find_method_declarations,
            parse_java_source,
        )

        source = "class Foo { public void process(String name, int count) {} }"
        tree = parse_java_source(source)
        for child in tree.root_node.children:
            if child.type == "class_declaration":
                methods = find_method_declarations(child, source.encode("utf-8"))
                assert len(methods) == 1
                params = methods[0]["parameters"]
                assert len(params) == 2
                assert params[0]["type"] == "String"
                assert params[0]["name"] == "name"
                assert params[1]["type"] == "int"
                return
        pytest.fail("No class_declaration found")

    def test_unwraps_generic_parameter_types(self) -> None:
        from invariant_guardian.rules.java_ast import (
            find_method_declarations,
            parse_java_source,
        )

        source = "class Foo { public List<OrderEntity> getOrders() { return null; } }"
        tree = parse_java_source(source)
        for child in tree.root_node.children:
            if child.type == "class_declaration":
                methods = find_method_declarations(child, source.encode("utf-8"))
                assert len(methods) == 1
                assert methods[0]["return_type"] == "List<OrderEntity>"
                # The type_arguments should include OrderEntity
                assert "type_arguments" in methods[0]
                type_args = methods[0]["type_arguments"]["return"] if methods[0]["type_arguments"] else []
                assert "OrderEntity" in type_args
                return
        pytest.fail("No class_declaration found")


# ---------------------------------------------------------------------------
# RED 5: find_method_calls — locate specific method invocations in a method body
# ---------------------------------------------------------------------------
class TestFindMethodCalls:
    """find_method_calls(method_node, target_methods, source) -> list[dict]"""

    def test_finds_schedule_call(self) -> None:
        from invariant_guardian.rules.java_ast import (
            find_method_calls,
            parse_java_source,
        )

        source = (
            "class Foo { void init() { "
            "executor.schedule(() -> work(), 5, TimeUnit.SECONDS); "
            "} }"
        )
        tree = parse_java_source(source)
        for child in tree.root_node.children:
            if child.type == "class_declaration":
                body = child.child_by_field_name("body")
                if body:
                    for member in body.children:
                        if member.type == "method_declaration":
                            calls = find_method_calls(
                                member, {"schedule", "scheduleAtFixedRate"},
                                source_bytes=source.encode("utf-8"),
                            )
                            assert len(calls) >= 1
                            assert calls[0]["method"] == "schedule"
                            return
        pytest.fail("No schedule call found")

    def test_returns_empty_when_no_match(self) -> None:
        from invariant_guardian.rules.java_ast import (
            find_method_calls,
            parse_java_source,
        )

        source = "class Foo { void init() { doWork(); } }"
        tree = parse_java_source(source)
        for child in tree.root_node.children:
            if child.type == "class_declaration":
                body = child.child_by_field_name("body")
                if body:
                    for member in body.children:
                        if member.type == "method_declaration":
                            calls = find_method_calls(
                                member, {"schedule"},
                                source_bytes=source.encode("utf-8"),
                            )
                            assert calls == []
                            return
        pytest.fail("No method found")


# ---------------------------------------------------------------------------
# RED 6: is_loop_statement — detect while(true) / for(;;) polling loops
# ---------------------------------------------------------------------------
class TestIsLoopStatement:
    """is_unbounded_loop(node, source) -> bool"""

    def test_detects_while_true_loop(self) -> None:
        from invariant_guardian.rules.java_ast import (
            is_unbounded_loop,
            parse_java_source,
        )

        source = "class Foo { void poll() { while (true) { check(); } } }"
        tree = parse_java_source(source)
        # Walk to find the while_statement
        def find_while(node):
            if node.type == "while_statement":
                return node
            for child in node.children:
                result = find_while(child)
                if result:
                    return result
            return None
        while_node = find_while(tree.root_node)
        assert while_node is not None
        assert is_unbounded_loop(while_node, source.encode("utf-8"))

    def test_detects_for_infinite_loop(self) -> None:
        from invariant_guardian.rules.java_ast import (
            is_unbounded_loop,
            parse_java_source,
        )

        source = "class Foo { void poll() { for (;;) { check(); } } }"
        tree = parse_java_source(source)

        def find_for(node):
            if node.type == "for_statement":
                return node
            for child in node.children:
                result = find_for(child)
                if result:
                    return result
            return None

        for_node = find_for(tree.root_node)
        assert for_node is not None
        assert is_unbounded_loop(for_node, source.encode("utf-8"))

    def test_bounded_for_loop_is_not_unbounded(self) -> None:
        from invariant_guardian.rules.java_ast import (
            is_unbounded_loop,
            parse_java_source,
        )

        source = "class Foo { void iter() { for (int i = 0; i < 10; i++) { work(); } } }"
        tree = parse_java_source(source)

        def find_for(node):
            if node.type == "for_statement":
                return node
            for child in node.children:
                result = find_for(child)
                if result:
                    return result
            return None

        for_node = find_for(tree.root_node)
        assert for_node is not None
        assert not is_unbounded_loop(for_node, source.encode("utf-8"))


# ---------------------------------------------------------------------------
# RED 7: has_sleep_or_backoff — detect Thread.sleep / TimeUnit.*.sleep in method
# ---------------------------------------------------------------------------
class TestHasSleepOrBackoff:
    """has_sleep_or_backoff(method_node, source) -> bool"""

    def test_detects_thread_sleep(self) -> None:
        from invariant_guardian.rules.java_ast import (
            has_sleep_or_backoff,
            parse_java_source,
        )

        source = "class Foo { void retry() { Thread.sleep(1000); } }"
        tree = parse_java_source(source)
        for child in tree.root_node.children:
            if child.type == "class_declaration":
                body = child.child_by_field_name("body")
                if body:
                    for member in body.children:
                        if member.type == "method_declaration":
                            assert has_sleep_or_backoff(member, source.encode("utf-8"))
                            return
        pytest.fail("No method found")

    def test_detects_timeunit_sleep(self) -> None:
        from invariant_guardian.rules.java_ast import (
            has_sleep_or_backoff,
            parse_java_source,
        )

        source = "class Foo { void retry() { TimeUnit.SECONDS.sleep(5); } }"
        tree = parse_java_source(source)
        for child in tree.root_node.children:
            if child.type == "class_declaration":
                body = child.child_by_field_name("body")
                if body:
                    for member in body.children:
                        if member.type == "method_declaration":
                            assert has_sleep_or_backoff(member, source.encode("utf-8"))
                            return
        pytest.fail("No method found")

    def test_no_sleep_returns_false(self) -> None:
        from invariant_guardian.rules.java_ast import (
            has_sleep_or_backoff,
            parse_java_source,
        )

        source = "class Foo { void work() { doStuff(); } }"
        tree = parse_java_source(source)
        for child in tree.root_node.children:
            if child.type == "class_declaration":
                body = child.child_by_field_name("body")
                if body:
                    for member in body.children:
                        if member.type == "method_declaration":
                            assert not has_sleep_or_backoff(member, source.encode("utf-8"))
                            return
        pytest.fail("No method found")


# ---------------------------------------------------------------------------
# RED 8: detect_domain_leak_candidates — AST-based domain-leak detection
# ---------------------------------------------------------------------------
class TestDetectDomainLeakCandidates:
    """detect_domain_leak_candidates(source: str, file_path: str,
    changed_lines: set[int]) -> list[CandidateFinding]"""

    def test_detects_entity_return_from_rest_controller(self) -> None:
        from invariant_guardian.rules.java_ast import detect_domain_leak_candidates

        source = (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class OrderController {\n"
            "    @GetMapping(\"/orders\")\n"
            "    public OrderEntity getOrder() { return null; }\n"
            "}\n"
        )
        candidates = detect_domain_leak_candidates(
            source, "src/OrderController.java", {5}
        )
        assert len(candidates) >= 1
        c = candidates[0]
        assert c["invariant_id"] == "no-domain-leak"
        assert c["file"] == "src/OrderController.java"

    def test_detects_entity_parameter_in_controller(self) -> None:
        from invariant_guardian.rules.java_ast import detect_domain_leak_candidates

        source = (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class OrderController {\n"
            "    @PostMapping(\"/orders\")\n"
            "    public void create(@RequestBody OrderEntity req) {}\n"
            "}\n"
        )
        candidates = detect_domain_leak_candidates(
            source, "src/OrderController.java", {5}
        )
        assert len(candidates) >= 1

    def test_detects_generic_entity_return(self) -> None:
        from invariant_guardian.rules.java_ast import detect_domain_leak_candidates

        source = (
            "import java.util.List;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class OrderController {\n"
            "    @GetMapping(\"/orders\")\n"
            "    public List<OrderEntity> getOrders() { return null; }\n"
            "}\n"
        )
        candidates = detect_domain_leak_candidates(
            source, "src/OrderController.java", {6}
        )
        assert len(candidates) >= 1

    def test_dto_return_is_clean(self) -> None:
        from invariant_guardian.rules.java_ast import detect_domain_leak_candidates

        source = (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class OrderController {\n"
            "    @GetMapping(\"/orders\")\n"
            "    public OrderResponse getOrder() { return null; }\n"
            "}\n"
        )
        candidates = detect_domain_leak_candidates(
            source, "src/OrderController.java", {5}
        )
        assert len(candidates) == 0

    def test_non_controller_class_is_not_checked(self) -> None:
        from invariant_guardian.rules.java_ast import detect_domain_leak_candidates

        source = (
            "class OrderService {\n"
            "    public OrderEntity getOrder() { return null; }\n"
            "}\n"
        )
        candidates = detect_domain_leak_candidates(
            source, "src/OrderService.java", {2}
        )
        # Not a controller — no Spring web annotations
        assert len(candidates) == 0

    def test_entity_class_annotation_detected_on_return_type(self) -> None:
        """When the return type is a class annotated with @Entity in the same
        source file, the detector should identify it."""
        from invariant_guardian.rules.java_ast import detect_domain_leak_candidates

        source = (
            "import jakarta.persistence.Entity;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@Entity\n"
            "class OrderEntity {}\n"
            "@RestController\n"
            "class OrderController {\n"
            "    @GetMapping(\"/orders\")\n"
            "    public OrderEntity getOrder() { return null; }\n"
            "}\n"
        )
        candidates = detect_domain_leak_candidates(
            source, "src/OrderController.java", {8}
        )
        assert len(candidates) >= 1


# ---------------------------------------------------------------------------
# RED 9: detect_monitoring_candidates — AST-based temporary-monitoring detection
# ---------------------------------------------------------------------------
class TestDetectMonitoringCandidates:
    """detect_monitoring_candidates(source: str, file_path: str,
    changed_lines: set[int]) -> list[CandidateFinding]"""

    def test_detects_scheduled_annotation(self) -> None:
        from invariant_guardian.rules.java_ast import detect_monitoring_candidates

        source = (
            "import org.springframework.scheduling.annotation.Scheduled;\n"
            "class OrderService {\n"
            "    @Scheduled(fixedDelay = 5000)\n"
            "    public void retryOrders() {\n"
            "        orderRepository.save(order);\n"
            "    }\n"
            "}\n"
        )
        candidates = detect_monitoring_candidates(
            source, "src/OrderService.java", {3, 4}
        )
        assert len(candidates) >= 1
        c = candidates[0]
        assert c["invariant_id"] == "no-temporary-monitoring"
        assert c["file"] == "src/OrderService.java"

    def test_detects_scheduled_executor_service(self) -> None:
        from invariant_guardian.rules.java_ast import detect_monitoring_candidates

        source = (
            "import java.util.concurrent.*;\n"
            "class OrderService {\n"
            "    void init() {\n"
            "        executor.schedule(() -> work(), 5, TimeUnit.SECONDS);\n"
            "    }\n"
            "}\n"
        )
        candidates = detect_monitoring_candidates(
            source, "src/OrderService.java", {4}
        )
        assert len(candidates) >= 1

    def test_detects_while_true_polling_with_state_change(self) -> None:
        from invariant_guardian.rules.java_ast import detect_monitoring_candidates

        source = (
            "class OrderService {\n"
            "    void poll() {\n"
            "        while (true) {\n"
            "            checkStatus();\n"
            "            orderRepository.save(order);\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        candidates = detect_monitoring_candidates(
            source, "src/OrderService.java", {3}
        )
        assert len(candidates) >= 1

    def test_detects_retry_with_sleep(self) -> None:
        from invariant_guardian.rules.java_ast import detect_monitoring_candidates

        source = (
            "class OrderService {\n"
            "    void retry() {\n"
            "        for (int i = 0; i < 3; i++) {\n"
            "            try { process(); break; }\n"
            "            catch (Exception e) {\n"
            "                Thread.sleep(1000);\n"
            "            }\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        candidates = detect_monitoring_candidates(
            source, "src/OrderService.java", {3}
        )
        assert len(candidates) >= 1

    def test_documented_daily_job_is_not_monitoring(self) -> None:
        """Intentional scheduled jobs (e.g. daily reconciliation) should not
        be flagged without a related state change in the same change."""
        from invariant_guardian.rules.java_ast import detect_monitoring_candidates

        source = (
            "import org.springframework.scheduling.annotation.Scheduled;\n"
            "class ReconciliationJob {\n"
            "    @Scheduled(cron = \"0 0 2 * * *\")\n"
            "    public void reconcile() {\n"
            "        report.generate();\n"
            "    }\n"
            "}\n"
        )
        candidates = detect_monitoring_candidates(
            source, "src/ReconciliationJob.java", {3, 4}
        )
        # Without a state-change signal (save/update/transition), this should
        # be a weaker candidate or not flagged for the "temporary" variant.
        # The detector may still flag @Scheduled as a candidate but the judge
        # should reject it. For now, at minimum the evidence must be clear.
        # If it IS detected, it should have lower confidence.
        for c in candidates:
            assert c["confidence"] in ("low", "medium")

    def test_no_state_change_no_candidate_for_polling(self) -> None:
        from invariant_guardian.rules.java_ast import detect_monitoring_candidates

        source = (
            "class HealthCheck {\n"
            "    void check() {\n"
            "        while (true) {\n"
            "            ping();\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        candidates = detect_monitoring_candidates(
            source, "src/HealthCheck.java", {3}
        )
        # polling alone without state change should not be a strong candidate
        for c in candidates:
            assert c["confidence"] != "high"
