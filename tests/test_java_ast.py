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
        import pytest

        from invariant_guardian.rules.java_ast import parse_java_source

        with pytest.raises(ValueError, match="ERROR"):
            parse_java_source("this is not java @@@")


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

        source = (
            "class Foo { void retry() { "
            "for (int i = 0; i < 3; i++) { Thread.sleep(1000); } "
            "} }"
        )
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

        source = (
            "class Foo { void retry() { "
            "for (int i = 0; i < 3; i++) { TimeUnit.SECONDS.sleep(5); } "
            "} }"
        )
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
            "        ScheduledExecutorService executor = Executors.newScheduledThreadPool(1);\n"
            "        executor.schedule(() -> work(), 5, TimeUnit.SECONDS);\n"
            "    }\n"
            "}\n"
        )
        candidates = detect_monitoring_candidates(
            source, "src/OrderService.java", {5}
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
            "            try { save(); break; }\n"
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
        # @Scheduled without state change must NOT produce any candidate —
        # documented batch jobs are intentional, not temporary monitoring.
        assert len(candidates) == 0, (
            f"@Scheduled without state change must not produce candidates: "
            f"got {candidates}"
        )

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


# ---------------------------------------------------------------------------
# RED: Changed-line offset false-cleans (P0 finding 1)
# ---------------------------------------------------------------------------
class TestChangedLineOffsetMapping:
    """Regression: reconstructed source lines must map to new-file line numbers.

    When a patch adds code at new-file line 96, the reconstructed source
    lines start at 1.  The AST reports methods at source-relative lines,
    but changed_lines uses new-file line numbers.  Without a line map,
    methods whose changed lines are far from the file start are skipped
    and the engine returns clean — a false negative.
    """

    def test_high_offset_method_is_detected(self) -> None:
        """A controller method added at new-file line 96 must be detected."""
        from invariant_guardian.rules.java import (
            detect_candidates_from_source,
            extract_changed_lines_from_patch,
            reconstruct_source_from_patch,
        )

        # Simulate a patch where a new controller method with entity return
        # is added near the end of an existing file (new-file line 96).
        #
        # Hunk: 5 context lines exist in both old and new file;
        # 4 lines are added.  New-file starts at line 96.
        #   context (5)=import,blank,@RestController,class,closing-brace
        #   added   (4)=@GetMapping,method sig,return,closing-brace
        # Old: 5 lines at -96,5   New: 9 lines at +96,9
        patch = (
            "@@ -96,5 +96,9 @@\n"
            " import org.springframework.web.bind.annotation.*;\n"
            " \n"
            " @RestController\n"
            " class OrderController {\n"
            "+    @GetMapping(\"/orders\")\n"
            "+    public List<OrderEntity> getOrders() {\n"
            "+        return repository.findOrders();\n"
            "+    }\n"
            " }\n"
        )

        source, line_map = reconstruct_source_from_patch(patch)
        changed_lines = extract_changed_lines_from_patch(patch)

        # The added lines are at new-file positions 100-103
        assert 100 in changed_lines, (
            f"Changed lines should include new-file line 100, got {changed_lines}"
        )

        candidates = detect_candidates_from_source(
            source,
            "src/OrderController.java",
            changed_lines,
            {"no-domain-leak"},
            source_to_new_line_map=line_map,
        )

        # BUG: Without a line map, the AST finds getOrders at
        # reconstructed line ~5-7 (after stripping headers/prefixes),
        # but changed_lines = {96, 97, 98, 99}.  The intersection is
        # empty → no candidate, false clean.
        assert len(candidates) >= 1, (
            f"Offset bug: expected >=1 domain-leak candidate for method "
            f"added at new-file line 96, got {len(candidates)}. "
            f"changed_lines={changed_lines}"
        )
        assert candidates[0].pattern == "public boundary exposes likely internal type"


# ---------------------------------------------------------------------------
# RED: Outbound offset mapping — emitted candidates in new-file coordinates
# ---------------------------------------------------------------------------
class TestOutboundOffsetMapping:
    """Emitted candidate start_line/end_line must be new-file coordinates,
    not source-relative coordinates.  Without reverse mapping, candidates
    report lines that don't exist at the repository location."""

    def test_candidate_coordinates_are_new_file_lines(self) -> None:
        """When a method is added at new-file line 96, the candidate
        start_line must be 96, not the source-relative line 3."""
        from invariant_guardian.rules.java import (
            detect_candidates_from_source,
            extract_changed_lines_from_patch,
            reconstruct_source_from_patch,
        )

        # Hunk adds a method around new-file line 96 (5 context + 4 added)
        patch = (
            "@@ -96,5 +96,9 @@\n"
            " import org.springframework.web.bind.annotation.*;\n"
            " \n"
            " @RestController\n"
            " class OrderController {\n"
            "+    @GetMapping(\"/orders\")\n"
            "+    public List<OrderEntity> getOrders() {\n"
            "+        return repository.findOrders();\n"
            "+    }\n"
            " }\n"
        )

        source, line_map = reconstruct_source_from_patch(patch)
        changed_lines = extract_changed_lines_from_patch(patch)

        candidates = detect_candidates_from_source(
            source,
            "src/OrderController.java",
            changed_lines,
            {"no-domain-leak"},
            source_to_new_line_map=line_map,
        )

        assert len(candidates) >= 1, (
            f"Expected ≥1 domain-leak candidate, got {len(candidates)}"
        )

        # The candidate's start_line must be in new-file coordinates,
        # around line 99 (96 + 3 context + 1st added line at index 3→new 99).
        # It must NOT be source-relative line 4.
        c = candidates[0]
        assert c.start_line >= 96, (
            f"start_line {c.start_line} is source-relative (should be new-file ≥96); "
            f"candidate: {c}"
        )
        assert c.end_line >= 96, (
            f"end_line {c.end_line} is source-relative (should be new-file ≥96)"
        )

    def test_multiple_hunks_each_map_correctly(self) -> None:
        """Two hunks at different offsets — each candidate must map to
        its correct new-file line."""
        from invariant_guardian.rules.java import reconstruct_source_from_patch

        # First hunk adds at line 10, second at line 200
        patch = (
            "@@ -10,0 +11,3 @@\n"
            "+import org.springframework.web.bind.annotation.*;\n"
            "+@RestController\n"
            "+class FirstController {\n"
            "+    @GetMapping(\"/first\")\n"
            "+    public OrderEntity first() { return null; }\n"
            "+}\n"
            "@@ -200,0 +204,3 @@\n"
            "+@RestController\n"
            "+class SecondController {\n"
            "+    @GetMapping(\"/second\")\n"
            "+    public OrderEntity second() { return null; }\n"
            "+}\n"
        )

        with pytest.raises(ValueError, match="Disjoint hunks"):
            reconstruct_source_from_patch(patch)


# ---------------------------------------------------------------------------
# RED: Naming-convention evidence must have resolved declaration (P0 finding 3)
# ---------------------------------------------------------------------------
class TestNamingConventionRequiresDeclaration:
    """Naming-suffix evidence is invalid without resolving the relevant
    declaration.  A naming-convention-only match that cannot resolve the
    type declaration must produce a low-confidence candidate (not
    confirmable).
    """

    def test_naming_without_declaration_is_low_confidence(self) -> None:
        """ProductEntity returned by a controller — naming convention only,
        no @Entity annotation or declaration in the source.  Must be low
        confidence, not medium."""
        from invariant_guardian.rules.java_ast import detect_domain_leak_candidates

        source = (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class ProductController {\n"
            "    @GetMapping(\"/product\")\n"
            "    public ProductEntity getProduct() { return null; }\n"
            "}\n"
        )
        candidates = detect_domain_leak_candidates(
            source, "src/ProductController.java", {5}
        )
        if candidates:
            for c in candidates:
                assert c.get("confidence") == "low", (
                    f"Naming-only candidate without declaration must be low, "
                    f"got {c.get('confidence')}: {c.get('evidence')}"
                )

    def test_naming_with_declaration_source_is_medium(self) -> None:
        """When SourceReader resolves the ProductEntity declaration (showing
        it IS a persistence type via JPA annotation), confidence upgrades
        to medium."""
        from invariant_guardian.rules.java_ast import detect_domain_leak_candidates

        source = (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class ProductController {\n"
            "    @GetMapping(\"/product\")\n"
            "    public ProductEntity getProduct() { return null; }\n"
            "}\n"
        )
        # Simulate a source reader that resolves the declaration
        declaration_map = {
            "ProductEntity": (
                "import jakarta.persistence.Entity;\n"
                "@Entity\n"
                "class ProductEntity { private Long id; }\n"
            ),
        }

        def fake_source_reader(type_name: str) -> str | None:
            return declaration_map.get(type_name)

        candidates = detect_domain_leak_candidates(
            source, "src/ProductController.java", {5},
            source_reader=fake_source_reader,
        )
        assert len(candidates) >= 1
        c = candidates[0]
        assert c.get("confidence") == "medium", (
            f"With declaration resolved, confidence should be medium, "
            f"got {c.get('confidence')}"
        )
        # Must include related evidence from the declaration
        assert "related_evidence" in c, "Must include related_evidence field"
        assert c["related_evidence"] is not None, (
            "Must supply bounded declaration evidence"
        )


# ---------------------------------------------------------------------------
# RED: Parser errors must fail closed (P1 finding 4)
# ---------------------------------------------------------------------------
class TestParserErrorFailClosed:
    """Tree-sitter ERROR nodes must cause the detectors to fail closed —
    partial recovery must never produce medium/high candidates or clean
    coverage for affected structures.
    """

    def test_malformed_source_fails_closed(self) -> None:
        """A truncated/malformed method signature must cause the parser to
        fail closed — raising ValueError so the engine falls back to
        conservative regex signals only."""
        import pytest

        from invariant_guardian.rules.java_ast import detect_domain_leak_candidates

        # Malformed source: truncated generic, missing closing brace
        source = (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class BrokenController {\n"
            "    @GetMapping(\"/broken\")\n"
            "    public List<\n    OrderEntity getBroken() {\n"  # malformed
            "}\n"
        )
        with pytest.raises(ValueError, match="ERROR"):
            detect_domain_leak_candidates(
                source, "src/BrokenController.java", {5}
            )

    def test_clean_source_still_detected(self) -> None:
        """Valid source must still produce candidates after the error check."""
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
        assert len(candidates) >= 1, (
            "Valid source must still produce candidates"
        )


# ---------------------------------------------------------------------------
# RED: Domain-boundary contract — P1 finding 5
# ---------------------------------------------------------------------------
class TestDomainBoundaryContract:
    """Domain-boundary must support class OR method web annotations,
    enforce public visibility, resolve qualified annotations, and
    preserve DTO/record/event/public-contract negatives."""

    def test_method_level_annotation_boundary(self) -> None:
        """A method annotated @GetMapping in an unannotated class must
        still be treated as a public boundary."""
        from invariant_guardian.rules.java_ast import detect_domain_leak_candidates

        source = (
            "import org.springframework.web.bind.annotation.*;\n"
            "class PlainClass {\n"
            "    @GetMapping(\"/api\")\n"
            "    public OrderEntity getOrder() { return null; }\n"
            "}\n"
        )
        candidates = detect_domain_leak_candidates(
            source, "src/PlainClass.java", {4}
        )
        assert len(candidates) >= 1, (
            "Method-level @GetMapping must be recognized as public boundary"
        )

    def test_private_method_not_public_exposure(self) -> None:
        """A private method in a @RestController must NOT be flagged as
        a public boundary leak."""
        from invariant_guardian.rules.java_ast import detect_domain_leak_candidates

        source = (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class OrderController {\n"
            "    private OrderEntity helper() { return null; }\n"
            "}\n"
        )
        candidates = detect_domain_leak_candidates(
            source, "src/OrderController.java", {4}
        )
        assert len(candidates) == 0, (
            f"Private method in controller must not be flagged: {candidates}"
        )

    def test_qualified_annotation_rest_controller(self) -> None:
        """@org.springframework.web.bind.annotation.RestController
        must be recognized."""
        from invariant_guardian.rules.java_ast import detect_domain_leak_candidates

        source = (
            "import jakarta.persistence.Entity;\n"
            "@Entity\n"
            "class OrderEntity {}\n"
            "@org.springframework.web.bind.annotation.RestController\n"
            "class OrderController {\n"
            "    public OrderEntity getOrder() { return null; }\n"
            "}\n"
        )
        candidates = detect_domain_leak_candidates(
            source, "src/OrderController.java", {6}
        )
        assert len(candidates) >= 1, (
            "Qualified @RestController must be recognized"
        )

    def test_record_declaration_not_flagged(self) -> None:
        """A record with Entity suffix must NOT be flagged by naming
        convention alone without resolved declaration."""
        from invariant_guardian.rules.java_ast import detect_domain_leak_candidates

        source = (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class OrderController {\n"
            "    @GetMapping(\"/orders\")\n"
            "    public OrderAggregate getOrder() { return null; }\n"
            "}\n"
            "record OrderAggregate(String id, int total) {}\n"
        )
        candidates = detect_domain_leak_candidates(
            source, "src/OrderController.java", {5}
        )
        # OrderAggregate is a record in the same file — must not produce
        # medium confidence without resolved declaration showing it's @Entity
        for c in candidates:
            if c.get("confidence") == "medium":
                assert False, (
                    f"Record declaration must not produce medium confidence: {c}"
                )


# ---------------------------------------------------------------------------
# RED: Related declaration validation — P1 finding 5
# ---------------------------------------------------------------------------
class TestRelatedDeclarationValidation:
    """Fetched related declarations must be parsed and validated before
    being accepted as related_evidence.  Invalid Java, records, DTOs,
    events, and public contracts must be rejected."""

    def test_invalid_java_declaration_is_rejected(self) -> None:
        """A source_reader returning non-Java text must NOT be accepted
        as valid related evidence."""
        from invariant_guardian.rules.java_ast import detect_domain_leak_candidates

        source = (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class ProductController {\n"
            "    @GetMapping(\"/product\")\n"
            "    public ProductEntity getProduct() { return null; }\n"
            "}\n"
        )

        def bad_reader(type_name: str) -> str | None:
            return "this is not Java and not a declaration"

        candidates = detect_domain_leak_candidates(
            source, "src/ProductController.java", {5},
            source_reader=bad_reader,
        )
        # Must NOT accept invalid Java as medium confidence
        for c in candidates:
            assert c.get("confidence") != "medium", (
                f"Invalid Java declaration must not be medium confidence: {c}"
            )

    def test_record_declaration_is_rejected(self) -> None:
        """A record declaration for a type must NOT be accepted as
        internal persistence evidence."""
        from invariant_guardian.rules.java_ast import detect_domain_leak_candidates

        source = (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class AggregateController {\n"
            "    @GetMapping(\"/agg\")\n"
            "    public OrderAggregate getAgg() { return null; }\n"
            "}\n"
        )

        def record_reader(type_name: str) -> str | None:
            return "record OrderAggregate(String x) {}"

        candidates = detect_domain_leak_candidates(
            source, "src/AggregateController.java", {5},
            source_reader=record_reader,
        )
        for c in candidates:
            assert c.get("confidence") != "medium", (
                f"Record declaration must not be medium confidence: {c}"
            )

    def test_mismatched_declaration_is_rejected(self) -> None:
        """A declaration that doesn't match the requested type name
        must be rejected."""
        from invariant_guardian.rules.java_ast import detect_domain_leak_candidates

        source = (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class ProductController {\n"
            "    @GetMapping(\"/product\")\n"
            "    public ProductEntity getProduct() { return null; }\n"
            "}\n"
        )

        def mismatch_reader(type_name: str) -> str | None:
            # Returns a declaration for a DIFFERENT type
            return (
                "import jakarta.persistence.Entity;\n"
                "@Entity\n"
                "class OtherEntity {}\n"
            )

        candidates = detect_domain_leak_candidates(
            source, "src/ProductController.java", {5},
            source_reader=mismatch_reader,
        )
        for c in candidates:
            assert c.get("confidence") != "medium", (
                f"Mismatched declaration must not be medium confidence: {c}"
            )

    def test_valid_jpa_declaration_is_accepted(self) -> None:
        """A valid @Entity class declaring the correct type name must be
        accepted as medium confidence with related_evidence."""
        from invariant_guardian.rules.java_ast import detect_domain_leak_candidates

        source = (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class ProductController {\n"
            "    @GetMapping(\"/product\")\n"
            "    public ProductEntity getProduct() { return null; }\n"
            "}\n"
        )

        def valid_reader(type_name: str) -> str | None:
            return (
                "import jakarta.persistence.Entity;\n"
                "@Entity\n"
                "class ProductEntity { private Long id; }\n"
            )

        candidates = detect_domain_leak_candidates(
            source, "src/ProductController.java", {5},
            source_reader=valid_reader,
        )
        assert len(candidates) >= 1
        c = candidates[0]
        assert c.get("confidence") == "medium", (
            f"Valid @Entity declaration must be medium: {c}"
        )
        assert c.get("related_evidence") is not None


# ---------------------------------------------------------------------------
# RED: Monitoring detector structural verification — P1 finding 6
# ---------------------------------------------------------------------------
class TestMonitoringStructuralVerification:
    """Monitoring detector must verify receiver/type evidence for
    scheduling calls, require sleep inside retry loop, and anchor
    candidates to changed structural additions."""

    def test_arbitrary_schedule_method_not_flagged(self) -> None:
        """A call to customThing.schedule() must NOT be flagged as
        ScheduledExecutorService — receiver type must be verified."""
        from invariant_guardian.rules.java_ast import detect_monitoring_candidates

        source = (
            "class Scheduler {\n"
            "    void run() {\n"
            "        customThing.schedule(task);\n"
            "    }\n"
            "}\n"
        )
        candidates = detect_monitoring_candidates(
            source, "src/Scheduler.java", {3}
        )
        # Without ScheduledExecutorService receiver evidence, no high-confidence
        for c in candidates:
            assert c.get("confidence") != "high", (
                f"Arbitrary schedule() must not be high confidence: {c}"
            )

    def test_sleep_without_retry_loop_is_low_only(self) -> None:
        """Thread.sleep outside a retry loop must NOT produce a
        confirmable retry candidate."""
        from invariant_guardian.rules.java_ast import detect_monitoring_candidates

        source = (
            "class Pauser {\n"
            "    void pause() throws InterruptedException {\n"
            "        Thread.sleep(100);\n"
            "    }\n"
            "}\n"
        )
        candidates = detect_monitoring_candidates(
            source, "src/Pauser.java", {3}
        )
        for c in candidates:
            assert c.get("confidence") == "low", (
                f"Sleep without retry loop must be low confidence: {c}"
            )

    def test_name_based_scheduler_receiver_rejected(self) -> None:
        """A variable named 'scheduler' but declared as a plain Object
        must NOT be treated as ScheduledExecutorService."""
        from invariant_guardian.rules.java_ast import detect_monitoring_candidates

        source = (
            "import java.util.concurrent.*;\n"
            "class TaskRunner {\n"
            "    void run() {\n"
            "        Object scheduler = new Object();\n"
            "        scheduler.schedule(task);\n"
            "    }\n"
            "}\n"
        )
        candidates = detect_monitoring_candidates(
            source, "src/TaskRunner.java", {5}
        )
        # Variable named 'scheduler' but declared as Object — not
        # ScheduledExecutorService
        for c in candidates:
            assert c.get("confidence") != "high", (
                f"Name-based receiver check must not produce high confidence: {c}"
            )

    def test_unchanged_scheduled_annotation_not_flagged(self) -> None:
        """When @Scheduled is pre-existing and only repository.save()
        is added, the method must NOT be flagged as monitoring —
        the scheduled-work structural node is unchanged."""
        from invariant_guardian.rules.java_ast import detect_monitoring_candidates

        source = (
            "import org.springframework.scheduling.annotation.Scheduled;\n"
            "class Worker {\n"
            "    @Scheduled(fixedDelay = 5000)\n"
            "    public void doWork() {\n"
            "        doSomething();\n"
            "        repository.save(result);\n"
            "    }\n"
            "}\n"
        )
        # Only the save() line (6) is changed — @Scheduled at line 3-4
        # is pre-existing
        candidates = detect_monitoring_candidates(
            source, "src/Worker.java", {6}
        )
        for c in candidates:
            if c.get("pattern") == "scheduled work":
                assert False, (
                    f"Unchanged @Scheduled with only state change added "
                    f"must not be flagged: {c}"
                )

    def test_retry_sleep_requires_same_loop_as_state_change(self) -> None:
        """Sleep in one loop + state change in a different loop must NOT
        be combined into a single retry candidate."""
        from invariant_guardian.rules.java_ast import detect_monitoring_candidates

        source = (
            "class Worker {\n"
            "    void process() {\n"
            "        for (int i = 0; i < 3; i++) {\n"
            "            try { Thread.sleep(100); } catch (Exception e) {}\n"
            "        }\n"
            "        repository.save(result);\n"
            "    }\n"
            "}\n"
        )
        # Sleep at line 4, save at line 6 — different scopes
        candidates = detect_monitoring_candidates(
            source, "src/Worker.java", {6}
        )
        for c in candidates:
            if c.get("pattern") == "wait retry":
                assert c.get("confidence") != "high", (
                    f"Sleep outside changed scope must not be high confidence: {c}"
                )


# ---------------------------------------------------------------------------
# Regression: _classify_type naming-suffix heuristic (supersedes _is_internal_type)
# ---------------------------------------------------------------------------
class TestClassifyTypeSuffixHeuristic:
    """The _classify_type function (not the removed _is_internal_type) handles
    naming-suffix-based internal-type detection when no source_reader is
    available.  All three _INTERNAL_TYPE_SUFFIXES must be recognized."""

    def test_all_internal_suffixes_detected(self) -> None:
        """Entity, PersistenceModel, and Aggregate suffixes must each produce
        a low-confidence domain-leak candidate when no source_reader resolves
        the declaration."""
        from invariant_guardian.rules.java_ast import detect_domain_leak_candidates

        template = (
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class Controller {{\n"
            "    @GetMapping(\"/api\")\n"
            "    public {suffix} get() {{ return null; }}\n"
            "}}\n"
        )

        for suffix in ("OrderEntity", "OrderPersistenceModel", "OrderAggregate"):
            source = template.format(suffix=suffix)
            candidates = detect_domain_leak_candidates(
                source, "src/Controller.java", {5},
            )
            assert len(candidates) >= 1, (
                f"Suffix {suffix} not detected by _classify_type heuristic: "
                f"got {len(candidates)} candidate(s)"
            )
            assert candidates[0].get("confidence") == "low", (
                f"Suffix {suffix}: expected low confidence without source_reader, "
                f"got {candidates[0].get('confidence')}"
            )
