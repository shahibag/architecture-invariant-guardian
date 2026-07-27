"""Java structural analysis via Tree-sitter — AST fact extraction without
compiling, running, or importing target-repository source.

Parsing is read-only: we parse a string buffer and walk the concrete syntax
tree.  No code from the target repository is ever executed.
"""

from __future__ import annotations

from typing import Any

import tree_sitter
import tree_sitter_java as tsjava

# ---------------------------------------------------------------------------
# One-time language initialisation
# ---------------------------------------------------------------------------

_LANGUAGE = tree_sitter.Language(tsjava.language())

_PARSER = tree_sitter.Parser()
_PARSER.language = _LANGUAGE


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_java_source(source: str) -> tree_sitter.Tree:
    """Parse a Java source string into a Tree-sitter concrete syntax tree.

    The caller owns the returned tree and must keep it alive while any
    :class:`tree_sitter.Node` derived from it is in use.
    """
    return _PARSER.parse(source.encode("utf-8"))


# ---------------------------------------------------------------------------
# Annotation detection
# ---------------------------------------------------------------------------

# Spring web annotations that mark a public API boundary
_SPRING_WEB_ANNOTATIONS: set[str] = {
    "RestController",
    "Controller",
    "RequestMapping",
    "GetMapping",
    "PostMapping",
    "PutMapping",
    "PatchMapping",
    "DeleteMapping",
}

# JPA annotations that mark internal persistence types
_JPA_ENTITY_ANNOTATIONS: set[str] = {
    "Entity",
    "MappedSuperclass",
    "Embeddable",
}


def find_annotations(
    node: tree_sitter.Node,
    annotation_names: set[str],
    source_bytes: bytes,
) -> list[dict[str, Any]]:
    """Return annotations on *node* whose simple name is in *annotation_names*.

    Covers both ``marker_annotation`` (no arguments, e.g. ``@Override``)
    and ``annotation`` (with arguments, e.g. ``@GetMapping("/api")``).

    Each result is a dict with ``name``, ``start_line``, and ``start_byte``.
    """
    results: list[dict[str, Any]] = []
    # The modifiers node may be a direct child or a named field depending on
    # the grammar version — try both.
    modifiers = node.child_by_field_name("modifiers")
    if modifiers is None:
        for child in node.children:
            if child.type == "modifiers":
                modifiers = child
                break
    if modifiers is None:
        return results
    for child in modifiers.children:
        if child.type in ("marker_annotation", "annotation"):
            # The annotation name is the first ``identifier`` child
            name = _annotation_name(child, source_bytes)
            if name is not None and name in annotation_names:
                results.append({
                    "name": name,
                    "start_line": child.start_point[0] + 1,
                    "start_byte": child.start_byte,
                })
    return results


def _annotation_name(
    annotation_node: tree_sitter.Node, source_bytes: bytes
) -> str | None:
    """Extract the simple annotation name from a marker_annotation or
    annotation node."""
    for child in annotation_node.children:
        if child.type == "identifier":
            return _node_text(child, source_bytes)
    return None


# ---------------------------------------------------------------------------
# Class / interface / enum / record declaration discovery
# ---------------------------------------------------------------------------

_DECLARATION_TYPES: set[str] = {
    "class_declaration",
    "interface_declaration",
    "enum_declaration",
    "record_declaration",
}

_KIND_MAP: dict[str, str] = {
    "class_declaration": "class",
    "interface_declaration": "interface",
    "enum_declaration": "enum",
    "record_declaration": "record",
}


def find_class_declarations(
    tree: tree_sitter.Tree, source_bytes: bytes
) -> list[dict[str, Any]]:
    """Walk the whole tree and return every top-level or nested type declaration.

    Each dict has ``name``, ``kind``, ``start_line``, ``start_byte``, and
    ``node_type``.
    """
    results: list[dict[str, Any]] = []
    _collect_declarations(tree.root_node, source_bytes, results)
    return results


def _collect_declarations(
    node: tree_sitter.Node,
    source_bytes: bytes,
    results: list[dict[str, Any]],
) -> None:
    for child in node.children:
        if child.type in _DECLARATION_TYPES:
            name_node = child.child_by_field_name("name")
            name = _node_text(name_node, source_bytes) if name_node else "<unnamed>"
            results.append({
                "name": name,
                "kind": _KIND_MAP.get(child.type, child.type),
                "start_line": child.start_point[0] + 1,
                "start_byte": child.start_byte,
                "node_type": child.type,
                "node": child,  # caller may use for further traversal
            })
        # Recurse into bodies for nested types
        if child.type in ("class_body", "enum_body", "record_body",
                          "interface_body", "block"):
            _collect_declarations(child, source_bytes, results)
        elif child.type in _DECLARATION_TYPES:
            # Already handled above, but recurse into their bodies too
            body = child.child_by_field_name("body")
            if body is not None:
                _collect_declarations(body, source_bytes, results)


# ---------------------------------------------------------------------------
# Method declaration discovery
# ---------------------------------------------------------------------------


def find_method_declarations(
    class_node: tree_sitter.Node, source_bytes: bytes
) -> list[dict[str, Any]]:
    """Return method declarations in *class_node*'s body.

    Each dict has: ``name``, ``return_type``, ``parameters``
    (list of ``{name, type}``), ``start_line``, ``start_byte``,
    ``type_arguments`` (dict with "return" and "parameters" keys listing
    extracted generic type argument names).
    """
    results: list[dict[str, Any]] = []
    body = class_node.child_by_field_name("body")
    if body is None:
        return results
    for child in body.children:
        if child.type == "method_declaration":
            method_info = _extract_method_info(child, source_bytes)
            results.append(method_info)
    return results


def _extract_method_info(
    node: tree_sitter.Node, source_bytes: bytes
) -> dict[str, Any]:
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node, source_bytes) if name_node else "<unnamed>"

    return_type = "void"
    return_type_args: list[str] = []
    type_node = node.child_by_field_name("type")
    if type_node is not None:
        return_type, return_type_args = _extract_type_with_args(type_node, source_bytes)

    parameters: list[dict[str, str]] = []
    param_type_args: list[str] = []
    params_node = node.child_by_field_name("parameters")
    if params_node is not None:
        for child in params_node.children:
            if child.type == "formal_parameter":
                param_info = _extract_parameter(child, source_bytes)
                parameters.append(param_info)
                # Collect type arguments from parameter types
                ptype_node = child.child_by_field_name("type")
                if ptype_node is not None:
                    _, p_args = _extract_type_with_args(ptype_node, source_bytes)
                    param_type_args.extend(p_args)

    type_arguments: dict[str, list[str]] = {
        "return": return_type_args,
        "parameters": param_type_args,
    }

    return {
        "name": name,
        "return_type": return_type,
        "parameters": parameters,
        "start_line": node.start_point[0] + 1,
        "end_line": node.end_point[0] + 1,
        "start_byte": node.start_byte,
        "type_arguments": type_arguments,
    }


def _extract_parameter(
    node: tree_sitter.Node, source_bytes: bytes
) -> dict[str, str]:
    name_node = node.child_by_field_name("name")
    param_name = _node_text(name_node, source_bytes) if name_node else "arg"
    type_node = node.child_by_field_name("type")
    param_type = _node_text(type_node, source_bytes) if type_node else "Object"
    return {"name": param_name, "type": param_type}


def _extract_type_with_args(
    node: tree_sitter.Node, source_bytes: bytes
) -> tuple[str, list[str]]:
    """Return (type_name, [type_argument_names]) for a type node.

    For ``List<OrderEntity>`` this returns ``("List<OrderEntity>", ["OrderEntity"])``.
    """
    type_name = _node_text(node, source_bytes)
    type_args: list[str] = []
    for child in node.children:
        if child.type == "type_arguments":
            for tc in child.children:
                if tc.type == "type_identifier":
                    type_args.append(_node_text(tc, source_bytes))
    return type_name, type_args


# ---------------------------------------------------------------------------
# Method-call discovery
# ---------------------------------------------------------------------------


def find_method_calls(
    method_node: tree_sitter.Node,
    target_methods: set[str],
    source_bytes: bytes,
) -> list[dict[str, Any]]:
    """Return method invocations in *method_node*'s body whose name is in
    *target_methods*.

    Each dict has ``method`` and ``start_line``.
    """
    results: list[dict[str, Any]] = []
    _collect_method_calls(method_node, target_methods, source_bytes, results)
    return results


def _collect_method_calls(
    node: tree_sitter.Node,
    target_methods: set[str],
    source_bytes: bytes,
    results: list[dict[str, Any]],
) -> None:
    for child in node.children:
        if child.type == "method_invocation":
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                called = _node_text(name_node, source_bytes)
                if called in target_methods:
                    results.append({
                        "method": called,
                        "start_line": child.start_point[0] + 1,
                    })
        _collect_method_calls(child, target_methods, source_bytes, results)


# ---------------------------------------------------------------------------
# Loop detection
# ---------------------------------------------------------------------------


def is_unbounded_loop(
    node: tree_sitter.Node, source_bytes: bytes
) -> bool:
    """Return True when *node* (a ``while_statement`` or ``for_statement``)
    appears to be an unbounded polling loop.

    Detects ``while (true)`` and ``for (;;)`` patterns.
    """
    if node.type == "while_statement":
        condition = node.child_by_field_name("condition")
        if condition is not None:
            cond_text = _node_text(condition, source_bytes)
            # "(true)" from parenthesized_expression
            if cond_text in ("true", "(true)"):
                return True
            # Also check if the parenthesized_expression contains true
            if condition.type == "parenthesized_expression":
                for child in condition.children:
                    if child.type == "true":
                        return True
    elif node.type == "for_statement":
        # for (;;) — all three parts are empty
        init = node.child_by_field_name("initializer")
        cond = node.child_by_field_name("condition")
        update = node.child_by_field_name("update")
        if init is None and cond is None and update is None:
            # Check children for the semicolons pattern: "(" ";" ";" ")"
            parts_text = _node_text(node, source_bytes)
            # for (;;) after stripping whitespace
            compact = "".join(parts_text.split())
            if compact.startswith("for(;;)"):
                return True
            # Also check child structure
            semicolons = [c for c in node.children if c.type == ";"]
            if len(semicolons) == 2:
                return True
    return False


# ---------------------------------------------------------------------------
# Sleep / backoff detection
# ---------------------------------------------------------------------------

_SLEEP_PATTERNS: dict[tuple[str, str], bool] = {
    ("Thread", "sleep"): True,
    ("TimeUnit", "sleep"): True,
}


def has_sleep_or_backoff(
    method_node: tree_sitter.Node, source_bytes: bytes
) -> bool:
    """Return True when the method body contains ``Thread.sleep(...)``
    or ``TimeUnit.*.sleep(...)`` calls.
    """
    return _search_sleep(method_node, source_bytes)


def _search_sleep(node: tree_sitter.Node, source_bytes: bytes) -> bool:
    for child in node.children:
        if child.type == "method_invocation":
            name_node = child.child_by_field_name("name")
            if name_node is not None and _node_text(name_node, source_bytes) == "sleep":
                obj = child.child_by_field_name("object")
                if obj is not None:
                    obj_text = _node_text(obj, source_bytes)
                    # "Thread.sleep" or "TimeUnit.SECONDS.sleep" etc.
                    if obj_text == "Thread" or obj_text.startswith("TimeUnit"):
                        return True
        if _search_sleep(child, source_bytes):
            return True
    return False


# ---------------------------------------------------------------------------
# State-change detection
# ---------------------------------------------------------------------------

_STATE_CHANGE_PATTERNS: set[str] = {
    "save",
    "update",
    "setStatus",
    "transition",
    "publishEvent",
    "emit",
    "persist",
    "merge",
    "flush",
}


def has_state_change_in_method(
    method_node: tree_sitter.Node, source_bytes: bytes
) -> bool:
    """Return True when the method body contains a call to a state-change
    method (save, update, persist, etc.).

    Recursively walks the entire method AST.
    """
    return has_state_change_in_tree(method_node, source_bytes)


def has_state_change_in_tree(
    node: tree_sitter.Node, source_bytes: bytes
) -> bool:
    """Recursively check if any method_invocation in *node* matches a
    state-change pattern."""
    for child in node.children:
        if child.type == "method_invocation":
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                called = _node_text(name_node, source_bytes)
                if called in _STATE_CHANGE_PATTERNS:
                    return True
        if has_state_change_in_tree(child, source_bytes):
            return True
    return False


# ---------------------------------------------------------------------------
# Detectors — AST-based candidate generation (spec §8)
# ---------------------------------------------------------------------------

# Naming convention suffixes that suggest an internal persistence type
_INTERNAL_TYPE_SUFFIXES: tuple[str, ...] = (
    "Entity",
    "PersistenceModel",
    "Aggregate",
)

# ScheduledExecutorService scheduling methods
_SCHEDULING_METHODS: set[str] = {
    "schedule",
    "scheduleAtFixedRate",
    "scheduleWithFixedDelay",
}


def detect_domain_leak_candidates(
    source: str,
    file_path: str,
    changed_lines: set[int],
) -> list[dict[str, Any]]:
    """Return domain-leak candidates from *source* using AST facts.

    Each candidate is a dict with keys matching :class:`CandidateFinding`
    fields: ``invariant_id``, ``file``, ``start_line``, ``end_line``,
    ``pattern``, ``evidence``, ``confidence``.

    Detection logic:
    1. Find classes with Spring web annotations (RestController, Controller,
       RequestMapping, etc.)
    2. For methods in those classes annotated with web mapping annotations,
       check return types and parameter types for internal-type evidence.
    3. Internal types are those annotated with JPA annotations (Entity,
       MappedSuperclass, Embeddable) in the same source, or matching
       naming conventions (Entity, PersistenceModel, Aggregate).
    """
    candidates: list[dict[str, Any]] = []
    source_bytes = source.encode("utf-8")

    tree = parse_java_source(source)

    # Build a set of internal types from the source
    internal_types = _build_internal_type_set(tree, source_bytes)

    # Find controller classes
    for decl in find_class_declarations(tree, source_bytes):
        class_node = decl.get("node")
        if class_node is None:
            continue

        # Check if this class is a Spring web controller
        web_anns = find_annotations(class_node, _SPRING_WEB_ANNOTATIONS, source_bytes)
        # Also check for @RequestMapping on class (makes it a controller)
        has_class_mapping = bool(find_annotations(
            class_node, {"RequestMapping"}, source_bytes
        ))
        is_controller = bool(web_anns)

        if not is_controller and not has_class_mapping:
            continue

        # Check methods in this controller
        methods = find_method_declarations(class_node, source_bytes)
        for method in methods:
            method_start = method["start_line"]
            method_end = method.get("end_line", method_start)

            # A method is "changed" if any changed line falls within its range.
            # When changed_lines is None, check all methods.
            # When it's explicitly empty, no method is changed — skip all.
            if changed_lines is not None:
                method_range = set(range(method_start, method_end + 1))
                if not changed_lines.intersection(method_range):
                    continue

            method_node_ref = _find_method_node(class_node, method["name"],
                                                source_bytes)
            if method_node_ref is None:
                continue

            # Check return type
            ret_type = method["return_type"]
            ret_type_args = method.get("type_arguments", {}).get("return", [])
            if _is_internal_type(ret_type, internal_types) or any(
                _is_internal_type(ta, internal_types) for ta in ret_type_args
            ):
                # Find the actual changed line for the evidence location
                if changed_lines:
                    changed_in_range = sorted(
                        changed_lines.intersection(set(range(method_start, method_end + 1)))
                    )
                    candidate_line = changed_in_range[0] if changed_in_range else method_start
                else:
                    candidate_line = method_start
                candidates.append({
                    "invariant_id": "no-domain-leak",
                    "file": file_path,
                    "start_line": candidate_line,
                    "end_line": candidate_line,
                    "pattern": "public boundary exposes likely internal type",
                    "evidence": (
                        f"Method {method['name']} returns {ret_type} "
                        f"which appears to be an internal domain/persistence type"
                    ),
                    "confidence": "medium",
                })
                continue

            # Check parameter types
            for param in method.get("parameters", []):
                ptype = param["type"]
                if _is_internal_type(ptype, internal_types):
                    if changed_lines:
                        changed_in_range = sorted(
                            changed_lines.intersection(set(range(method_start, method_end + 1)))
                        )
                        candidate_line = changed_in_range[0] if changed_in_range else method_start
                    else:
                        candidate_line = method_start
                    candidates.append({
                        "invariant_id": "no-domain-leak",
                        "file": file_path,
                        "start_line": candidate_line,
                        "end_line": candidate_line,
                        "pattern": "public boundary exposes likely internal type",
                        "evidence": (
                            f"Method {method['name']} accepts {ptype} "
                            f"which appears to be an internal domain/persistence type"
                        ),
                        "confidence": "medium",
                    })
                    break

    return candidates


def _build_internal_type_set(
    tree: tree_sitter.Tree, source_bytes: bytes
) -> set[str]:
    """Collect type names that are annotated with JPA internal annotations."""
    internal: set[str] = set()
    for decl in find_class_declarations(tree, source_bytes):
        class_node = decl.get("node")
        if class_node is None:
            continue
        jpa_anns = find_annotations(
            class_node, _JPA_ENTITY_ANNOTATIONS, source_bytes
        )
        if jpa_anns:
            internal.add(decl["name"])
    return internal


def _is_internal_type(type_name: str, known_internal: set[str]) -> bool:
    """Check if *type_name* looks like an internal type."""
    if type_name in known_internal:
        return True
    # Strip generic wrapper to check the type argument
    if type_name.endswith(">"):
        # For "List<OrderEntity>" check "OrderEntity"
        inner = type_name.split("<", 1)[-1].rstrip(">")
        if inner in known_internal:
            return True
        if inner.endswith(_INTERNAL_TYPE_SUFFIXES):
            return True
    return bool(type_name.endswith(_INTERNAL_TYPE_SUFFIXES))


def _find_method_node(
    class_node: tree_sitter.Node, method_name: str, source_bytes: bytes
) -> tree_sitter.Node | None:
    """Locate the method_declaration node with the given name."""
    body = class_node.child_by_field_name("body")
    if body is None:
        return None
    for child in body.children:
        if child.type == "method_declaration":
            name_node = child.child_by_field_name("name")
            if name_node is not None and _node_text(name_node, source_bytes) == method_name:
                return child
    return None


def detect_monitoring_candidates(
    source: str,
    file_path: str,
    changed_lines: set[int],
) -> list[dict[str, Any]]:
    """Return temporary-monitoring candidates from *source* using AST facts.

    Detection logic:
    1. @Scheduled methods (high confidence with state change, low without)
    2. ScheduledExecutorService scheduling calls (high confidence)
    3. Unbounded polling loops (while(true), for(;;)) with state changes
    4. Retry loops containing sleep/backoff calls (high with state change,
       low without)
    """
    candidates: list[dict[str, Any]] = []
    source_bytes = source.encode("utf-8")

    tree = parse_java_source(source)
    for decl in find_class_declarations(tree, source_bytes):
        class_node = decl.get("node")
        if class_node is None:
            continue

        methods = find_method_declarations(class_node, source_bytes)
        for method in methods:
            method_start = method["start_line"]
            method_end = method.get("end_line", method_start)

            # Filter by changed lines: when changed_lines is explicitly
            # empty, no method is "changed" and we skip all.
            # When changed_lines has entries, only methods overlapping
            # with changed lines are considered.
            if changed_lines is not None:
                method_range = set(range(method_start, method_end + 1))
                if not changed_lines.intersection(method_range):
                    continue

            method_node_ref = _find_method_node(class_node, method["name"],
                                                source_bytes)
            if method_node_ref is None:
                continue

            # Find the actual changed line for evidence location.
            # When changed_lines is None, default to the method start line.
            if changed_lines:
                changed_in_range = sorted(
                    changed_lines.intersection(set(range(method_start, method_end + 1)))
                )
                candidate_line = changed_in_range[0] if changed_in_range else method_start
            else:
                candidate_line = method_start

            # 1. @Scheduled methods
            sched_anns = find_annotations(
                method_node_ref, {"Scheduled"}, source_bytes
            )
            if sched_anns:
                has_state = has_state_change_in_method(method_node_ref,
                                                       source_bytes)
                candidates.append({
                    "invariant_id": "no-temporary-monitoring",
                    "file": file_path,
                    "start_line": candidate_line,
                    "end_line": candidate_line,
                    "pattern": "scheduled work",
                    "evidence": (
                        f"Scheduled method {method['name']} "
                        + ("with state change" if has_state else "without state change")
                    ),
                    "confidence": "high" if has_state else "low",
                })
                continue

            # 2. ScheduledExecutorService calls
            sched_calls = find_method_calls(
                method_node_ref, _SCHEDULING_METHODS, source_bytes
            )
            if sched_calls:
                candidates.append({
                    "invariant_id": "no-temporary-monitoring",
                    "file": file_path,
                    "start_line": candidate_line,
                    "end_line": candidate_line,
                    "pattern": "scheduled work",
                    "evidence": (
                        f"Method {method['name']} calls "
                        f"executor.{sched_calls[0]['method']}()"
                    ),
                    "confidence": "high",
                })
                continue

            # 3. Unbounded polling loops with state changes
            unbounded = _find_unbounded_loops(method_node_ref, source_bytes)
            if unbounded:
                has_sc = has_state_change_in_tree(method_node_ref, source_bytes)
                if has_sc:
                    candidates.append({
                        "invariant_id": "no-temporary-monitoring",
                        "file": file_path,
                        "start_line": candidate_line,
                        "end_line": candidate_line,
                        "pattern": "state polling",
                        "evidence": (
                            f"Method {method['name']} contains an unbounded "
                            f"polling loop with state-change calls"
                        ),
                        "confidence": "medium",
                    })
                    continue

            # 4. Retry loops with sleep/backoff
            has_sleep = has_sleep_or_backoff(method_node_ref, source_bytes)
            if has_sleep:
                has_sc = has_state_change_in_tree(method_node_ref, source_bytes)
                candidates.append({
                    "invariant_id": "no-temporary-monitoring",
                    "file": file_path,
                    "start_line": candidate_line,
                    "end_line": candidate_line,
                    "pattern": "wait retry",
                    "evidence": (
                        f"Method {method['name']} contains sleep/backoff"
                        + (" with state-change calls" if has_sc else "")
                    ),
                    "confidence": "high" if has_sc else "low",
                })

    return candidates


def _find_unbounded_loops(
    node: tree_sitter.Node, source_bytes: bytes
) -> list[tree_sitter.Node]:
    """Find all unbounded loop nodes (while(true), for(;;)) in *node*."""
    results: list[tree_sitter.Node] = []
    for child in node.children:
        if child.type in ("while_statement", "for_statement") and is_unbounded_loop(
            child, source_bytes
        ):
            results.append(child)
        results.extend(_find_unbounded_loops(child, source_bytes))
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _node_text(node: tree_sitter.Node, source_bytes: bytes) -> str:
    """Return the source text spanned by *node*."""
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8")
