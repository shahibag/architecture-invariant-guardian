"""Java structural analysis via Tree-sitter — AST fact extraction without
compiling, running, or importing target-repository source.

Parsing is read-only: we parse a string buffer and walk the concrete syntax
tree.  No code from the target repository is ever executed.
"""

from __future__ import annotations

from collections.abc import Callable
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

    Raises :class:`ValueError` when the root node contains an ERROR or
    MISSING node — partial recovery must not produce confirmable structural
    evidence.
    """
    tree = _PARSER.parse(source.encode("utf-8"))
    if tree.root_node.has_error:
        raise ValueError(
            "Java parse produced ERROR/MISSING node — "
            "structural evidence is unreliable"
        )
    return tree


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
    annotation node.

    Handles unqualified (``@RestController``) and qualified
    (``@org.springframework.web.bind.annotation.RestController``) forms.
    """
    for child in annotation_node.children:
        if child.type == "identifier":
            return _node_text(child, source_bytes)
        if child.type == "scoped_identifier":
            # Qualified: @org.foo.Bar — the last segment is the simple name
            text = _node_text(child, source_bytes)
            return text.rsplit(".", 1)[-1] if "." in text else text
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
    receiver_check: str | None = None,
) -> list[dict[str, Any]]:
    """Return method invocations in *method_node*'s body whose name is in
    *target_methods*.

    When *receiver_check* is provided, the receiver (object) of the call
    must be of a type whose name ends with *receiver_check* (e.g.
    ``"ScheduledExecutorService"``).

    Each dict has ``method`` and ``start_line``.
    """
    results: list[dict[str, Any]] = []
    _collect_method_calls(
        method_node, target_methods, source_bytes, results, receiver_check,
        method_node,  # pass method context for variable lookup
    )
    return results


def _collect_method_calls(
    node: tree_sitter.Node,
    target_methods: set[str],
    source_bytes: bytes,
    results: list[dict[str, Any]],
    receiver_check: str | None = None,
    method_context: tree_sitter.Node | None = None,
) -> None:
    for child in node.children:
        if child.type == "method_invocation":
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                called = _node_text(name_node, source_bytes)
                if called in target_methods:
                    # When receiver_check is specified, verify the receiver
                    if receiver_check is not None:
                        obj_node = child.child_by_field_name("object")
                        receiver_match = _check_receiver(
                            obj_node, receiver_check, source_bytes,
                            method_context,
                        )
                        if not receiver_match:
                            continue
                    results.append({
                        "method": called,
                        "start_line": child.start_point[0] + 1,
                    })
        _collect_method_calls(child, target_methods, source_bytes, results,
                             receiver_check, method_context)


def _check_receiver(
    obj_node: tree_sitter.Node | None,
    receiver_check: str,
    source_bytes: bytes,
    method_context: tree_sitter.Node | None = None,
) -> bool:
    """Check whether *obj_node* is of a type matching *receiver_check*.

    Resolves the receiver type from local-variable, formal parameter,
    and field declarations within the enclosing method and class.
    Never relies on variable-name heuristics — the declared type must
    carry *receiver_check*.
    """
    if obj_node is None:
        return False
    obj_text = _node_text(obj_node, source_bytes)
    if method_context is None:
        return False

    # Collect all declaration sites: local vars, params, and fields
    candidates: list[tree_sitter.Node] = list(_traverse_all(method_context))
    # Also traverse up to find the enclosing class body for fields
    parent = method_context.parent
    while parent is not None:
        if parent.type in ("class_body", "enum_body", "record_body", "interface_body"):
            candidates.extend(_traverse_all(parent))
            break
        parent = parent.parent

    for child in candidates:
        if child.type == "local_variable_declaration":
            decl_type = child.child_by_field_name("type")
            if decl_type is not None:
                type_text = _node_text(decl_type, source_bytes)
                if type_text.endswith(receiver_check):
                    declarator = child.child_by_field_name("declarator")
                    if declarator is not None:
                        # Use the declarator's name child, not full text
                        # (which includes the initializer)
                        name_node = declarator.child_by_field_name("name")
                        var_name = (
                            _node_text(name_node, source_bytes)
                            if name_node else _node_text(declarator, source_bytes)
                        )
                        if var_name == obj_text:
                            return True
        elif child.type == "formal_parameter":
            decl_type = child.child_by_field_name("type")
            if decl_type is not None:
                type_text = _node_text(decl_type, source_bytes)
                if type_text.endswith(receiver_check):
                    name_node = child.child_by_field_name("name")
                    if name_node is not None:
                        var_name = _node_text(name_node, source_bytes)
                        if var_name == obj_text:
                            return True
        elif child.type == "field_declaration":
            decl_type = child.child_by_field_name("type")
            if decl_type is not None:
                type_text = _node_text(decl_type, source_bytes)
                if type_text.endswith(receiver_check):
                    declarator = child.child_by_field_name("declarator")
                    if declarator is not None:
                        name_node = declarator.child_by_field_name("name")
                        var_name = (
                            _node_text(name_node, source_bytes)
                            if name_node else _node_text(declarator, source_bytes)
                        )
                        if var_name == obj_text:
                            return True
    return False


def _traverse_all(node: tree_sitter.Node) -> list[tree_sitter.Node]:
    """Yield all descendants of *node* (depth-first)."""
    nodes: list[tree_sitter.Node] = []
    for child in node.children:
        nodes.append(child)
        nodes.extend(_traverse_all(child))
    return nodes


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
    or ``TimeUnit.*.sleep(...)`` calls inside a loop body (retry pattern).
    """
    return _search_sleep(method_node, source_bytes, require_loop=True)


def _search_sleep(
    node: tree_sitter.Node,
    source_bytes: bytes,
    require_loop: bool = False,
    in_loop: bool = False,
) -> bool:
    is_loop = node.type in (
        "for_statement", "while_statement", "do_statement",
        "enhanced_for_statement",
    )
    next_in_loop = in_loop or is_loop

    for child in node.children:
        if child.type == "method_invocation":
            name_node = child.child_by_field_name("name")
            if (
                name_node is not None
                and _node_text(name_node, source_bytes) == "sleep"
                and (not require_loop or next_in_loop)
            ):
                    obj = child.child_by_field_name("object")
                    if obj is not None:
                        obj_text = _node_text(obj, source_bytes)
                        if obj_text == "Thread" or obj_text.startswith("TimeUnit"):
                            return True
        if _search_sleep(child, source_bytes, require_loop, next_in_loop):
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
    source_reader: Callable[[str], str | None] | None = None,
) -> list[dict[str, Any]]:
    """Return domain-leak candidates from *source* using AST facts.

    Each candidate is a dict with keys matching :class:`CandidateFinding`
    fields: ``invariant_id``, ``file``, ``start_line``, ``end_line``,
    ``pattern``, ``evidence``, ``confidence``, and ``related_evidence``.

    *source_reader* is an optional callable ``(type_name) -> str | None``
    that resolves type declarations.  When absent, naming-convention-only
    matches are low confidence (speculative).

    P0 finding 2: Types without internal naming suffixes are resolved via
    *source_reader* before classification.  A separately declared
    ``@Entity`` type named ``Order`` is detected; a record, DTO, or
    non-JPA class is correctly excluded.
    """
    candidates: list[dict[str, Any]] = []
    source_bytes = source.encode("utf-8")

    tree = parse_java_source(source)

    declarations = find_class_declarations(tree, source_bytes)

    # Build a set of internal types from the source
    internal_types = _build_internal_type_set(tree, source_bytes)

    # Every valid same-file declaration not marked JPA-internal is an
    # acceptable public/DTO contract, regardless of a misleading suffix.
    acceptable_names = {d["name"] for d in declarations} - internal_types

    # Find controller classes
    for decl in declarations:
        class_node = decl.get("node")
        if class_node is None:
            continue

        # Check if this class is a Spring web controller
        web_anns = find_annotations(class_node, _SPRING_WEB_ANNOTATIONS, source_bytes)
        has_class_mapping = bool(find_annotations(
            class_node, {"RequestMapping"}, source_bytes
        ))
        is_controller = bool(web_anns) or has_class_mapping

        # Check methods in this class
        methods = find_method_declarations(class_node, source_bytes)
        for method in methods:
            method_start = method["start_line"]
            method_end = method.get("end_line", method_start)

            # A method is "changed" if any changed line falls within its range.
            if changed_lines is not None:
                method_range = set(range(method_start, method_end + 1))
                if not changed_lines.intersection(method_range):
                    continue

            method_node_ref = _find_method_node(class_node, method["name"],
                                                source_bytes)
            if method_node_ref is None:
                continue

            # Public visibility check — only publicly accessible methods
            # can leak internal types at a public boundary.
            if not _is_public_method(method_node_ref, source_bytes):
                continue

            # Method-level boundary: a method annotated with a web mapping
            # annotation is a public boundary even when the enclosing class
            # lacks a controller annotation.
            if not is_controller:
                method_web_anns = find_annotations(
                    method_node_ref, _SPRING_WEB_ANNOTATIONS, source_bytes
                )
                if not method_web_anns:
                    continue

            if changed_lines:
                changed_in_range = sorted(
                    changed_lines.intersection(set(range(method_start, method_end + 1)))
                )
                candidate_line = changed_in_range[0] if changed_in_range else method_start
            else:
                candidate_line = method_start

            # --- Check return type ---
            ret_type = method["return_type"]
            ret_type_args = method.get("type_arguments", {}).get("return", [])
            outcome = _classify_type(ret_type, internal_types, acceptable_names,
                                     source_reader)
            # Also check type arguments
            if outcome == "acceptable":
                for ta in ret_type_args:
                    outcome = _classify_type(ta, internal_types, acceptable_names,
                                             source_reader)
                    if outcome in ("internal", "unavailable"):
                        ret_type = ta
                        break

            if outcome == "internal":
                _add_domain_leak_candidate(
                    candidates, file_path, candidate_line,
                    method["name"], ret_type, "returns",
                    internal_types, source_reader,
                )
                continue
            if outcome == "unavailable":
                _add_domain_leak_candidate(
                    candidates, file_path, candidate_line,
                    method["name"], ret_type, "returns",
                    internal_types, source_reader,
                )
                continue

            # --- Check parameter types ---
            for param in method.get("parameters", []):
                ptype = param["type"]
                outcome = _classify_type(ptype, internal_types, acceptable_names,
                                         source_reader)
                if outcome in ("internal", "unavailable"):
                    _add_domain_leak_candidate(
                        candidates, file_path, candidate_line,
                        method["name"], ptype, "accepts",
                        internal_types, source_reader,
                    )
                    break

    return candidates


def _add_domain_leak_candidate(
    candidates: list[dict[str, Any]],
    file_path: str,
    candidate_line: int,
    method_name: str,
    type_name: str,
    direction: str,
    internal_types: set[str],
    source_reader: Callable[[str], str | None] | None,
) -> None:
    """Build and append a domain-leak candidate with appropriate confidence.

    Same-file JPA-annotated → medium confidence.
    Naming-convention with resolved declaration → medium confidence.
    Naming-convention without resolution → low confidence.
    """
    related_evidence: str | None = None

    # Determine confidence level
    # Strip generic wrappers for matching: "List<OrderEntity>" → "OrderEntity"
    simple_type = type_name
    if "<" in simple_type:
        simple_type = simple_type.split("<", 1)[-1].rstrip(">")
    if type_name in internal_types or simple_type in internal_types:
        # Same-file JPA-annotated — confirmed internal
        confidence = "medium"
    elif source_reader is not None:
        # Naming convention or no-suffix — try to resolve and validate.
        # Use the simple type name (without generics) for resolution.
        declaration, _ = _resolve_type_from_source(simple_type, source_reader)
        if declaration is not None and _validate_related_declaration(
            declaration, type_name
        ):
            related_evidence = (
                f"Declaration of {type_name}:\n{declaration}"
            )
            # Truncate declaration to a bounded size
            max_decl_bytes = 100_000  # MAX_SOURCE_BYTES_PER_FILE
            decl_bytes = related_evidence.encode("utf-8")
            if len(decl_bytes) > max_decl_bytes:
                related_evidence = (
                    decl_bytes[:max_decl_bytes].decode("utf-8", errors="replace")
                    + "\n[truncated]"
                )
            confidence = "medium"
        else:
            confidence = "low"
    else:
        confidence = "low"

    candidate: dict[str, Any] = {
        "invariant_id": "no-domain-leak",
        "file": file_path,
        "start_line": candidate_line,
        "end_line": candidate_line,
        "pattern": "public boundary exposes likely internal type",
        "evidence": (
            f"Method {method_name} {direction} {type_name} "
            f"which appears to be an internal domain/persistence type"
        ),
        "confidence": confidence,
        "related_evidence": related_evidence,
    }
    candidates.append(candidate)


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


def _is_internal_type(type_name: str, known_internal: set[str]) -> tuple[bool, str | None]:
    """Check if *type_name* looks like an internal type.

    Returns ``(is_internal, naming_suffix)`` where *naming_suffix* is the
    matched suffix when the match was via naming convention rather than a
    known JPA-annotated type.
    """
    if type_name in known_internal:
        return True, None
    # Strip generic wrapper to check the type argument
    if type_name.endswith(">"):
        # For "List<OrderEntity>" check "OrderEntity"
        inner = type_name.split("<", 1)[-1].rstrip(">")
        if inner in known_internal:
            return True, None
        if inner.endswith(_INTERNAL_TYPE_SUFFIXES):
            for suffix in _INTERNAL_TYPE_SUFFIXES:
                if inner.endswith(suffix):
                    return True, suffix
    for suffix in _INTERNAL_TYPE_SUFFIXES:
        if type_name.endswith(suffix):
            return True, suffix
    return False, None


# ---------------------------------------------------------------------------
# P0 finding 2: typed resolution outcome
# ---------------------------------------------------------------------------

_ResolutionOutcome = str  # "internal" | "acceptable" | "unavailable"


def _classify_type(
    type_name: str,
    known_internal: set[str],
    acceptable_names: set[str],
    source_reader: Callable[[str], str | None] | None,
) -> _ResolutionOutcome:
    """Classify *type_name* as internal, acceptable, or unavailable.

    Resolution order:
    1. Same-file JPA-annotated declaration → internal.
    2. Other valid same-file declarations → acceptable.
    3. With a source reader, resolve and structurally classify the declaration:
       JPA class → internal; record/enum/interface/non-JPA class → acceptable;
       missing/malformed/mismatched evidence → unavailable.
    4. Without a source reader only, retain the legacy suffix heuristic.
    """
    simple = type_name.split("<", 1)[-1].rstrip(">").rsplit(".", 1)[-1]
    if simple in {
        "void", "boolean", "byte", "short", "int", "long", "float", "double",
        "char", "String", "Object", "UUID", "BigDecimal", "BigInteger",
        "List", "Set", "Map", "Collection", "Iterable", "Optional",
        "ResponseEntity", "HttpStatus",
    }:
        return "acceptable"

    # 1 & 2: same-file classification
    if type_name in known_internal:
        return "internal"
    if type_name in acceptable_names or simple in acceptable_names:
        return "acceptable"

    # Resolve before applying any naming heuristic. A valid DTO/record named
    # ``*Entity`` is acceptable, while missing or malformed required evidence
    # is unavailable rather than clean.
    if source_reader is not None:
        declaration, _ = _resolve_type_from_source(simple, source_reader)
        if declaration is None:
            return "unavailable"
        try:
            decl_tree = parse_java_source(declaration)
        except ValueError:
            return "unavailable"
        decl_bytes = declaration.encode("utf-8")
        decls = find_class_declarations(decl_tree, decl_bytes)
        for d in decls:
            if d["name"] != simple:
                continue
            kind = d.get("kind", "class")
            if kind in ("record", "enum", "interface"):
                return "acceptable"
            if kind == "class":
                class_node = d.get("node")
                if class_node is None:
                    return "unavailable"
                jpa_anns = find_annotations(
                    class_node, _JPA_ENTITY_ANNOTATIONS, decl_bytes
                )
                return "internal" if jpa_anns else "acceptable"
        return "unavailable"

    # Legacy direct/local callers without repository source access retain the
    # conservative suffix candidate; production Action always supplies a reader.
    if simple.endswith(_INTERNAL_TYPE_SUFFIXES):
        return "internal"
    return "acceptable"


def _validate_related_declaration(declaration: str, type_name: str) -> bool:
    """Validate a related declaration retrieved from a SourceReader.

    The declaration must:
    1. Parse as valid Java (no ERROR/MISSING nodes)
    2. Declare *type_name* as a type (class, not record/enum/interface)
    3. Carry a supported JPA annotation (@Entity, @MappedSuperclass,
       @Embeddable)

    Returns ``False`` for records, DTOs, events, public contracts,
    malformed Java, or mismatched type names.
    """
    try:
        tree = parse_java_source(declaration)
    except ValueError:
        # Parser error — invalid Java
        return False

    source_bytes = declaration.encode("utf-8")
    decls = find_class_declarations(tree, source_bytes)

    for d in decls:
        if d["name"] != type_name:
            continue
        # Must be a class, not record/enum/interface
        if d.get("kind") != "class":
            return False
        # Must have JPA annotation evidence
        class_node = d.get("node")
        if class_node is None:
            return False
        jpa_anns = find_annotations(
            class_node, _JPA_ENTITY_ANNOTATIONS, source_bytes
        )
        return bool(jpa_anns)

    # Type name not found in the declaration
    return False


def _resolve_type_from_source(
    type_name: str,
    source_reader: Callable[[str], str | None] | None,
) -> tuple[str | None, str | None]:
    """Try to resolve *type_name*'s declaration via *source_reader*.

    *source_reader* is ``(type_name: str) -> str | None`` — a callable
    that returns the declaration source for a type name, or None when
    unresolvable.

    Returns ``(declaration_source, type_name)`` or ``(None, None)``.
    """
    if source_reader is None:
        return None, None
    try:
        resolved = source_reader(type_name)
        if resolved is not None:
            return resolved, type_name
    except Exception:  # noqa: BLE001 — source reader is an untrusted boundary
        return None, None
    return None, None


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


def _is_public_method(
    method_node: tree_sitter.Node, source_bytes: bytes
) -> bool:
    """Return True when the method declaration has a ``public`` modifier."""
    modifiers = method_node.child_by_field_name("modifiers")
    if modifiers is None:
        for child in method_node.children:
            if child.type == "modifiers":
                modifiers = child
                break
    if modifiers is None:
        return False
    for child in modifiers.children:
        if child.type == "public":
            return True
    return False


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

            # 1. @Scheduled methods — only flag when accompanied by
            # a state-change call (save/update/transition/persist/etc).
            # @Scheduled alone (e.g. documented daily reconciliation)
            # is intentional batch work, not temporary monitoring.
            # The @Scheduled annotation itself must intersect changed
            # lines — an unchanged @Scheduled with only a state change
            # added elsewhere is not a monitoring addition.
            sched_anns = find_annotations(
                method_node_ref, {"Scheduled"}, source_bytes
            )
            if sched_anns:
                # Verify annotation itself intersects changed lines
                sched_changed = changed_lines is not None and any(
                    ann["start_line"] in changed_lines
                    for ann in sched_anns
                )
                if not sched_changed and changed_lines is not None:
                    # @Scheduled is pre-existing — the structural
                    # node was not added in this change
                    continue
                has_state = has_state_change_in_method(method_node_ref,
                                                       source_bytes)
                if has_state:
                    state_lines = sorted(
                        _find_state_change_lines(method_node_ref, source_bytes)
                    )
                    if not state_lines:
                        continue
                    state_line = state_lines[0]
                    source_line = source.splitlines()[state_line - 1].strip()
                    candidates.append({
                        "invariant_id": "no-temporary-monitoring",
                        "file": file_path,
                        "start_line": sched_anns[0]["start_line"],
                        "end_line": state_line,
                        "pattern": "scheduled work",
                        "evidence": (
                            f"Scheduled method {method['name']} "
                            "with state change"
                        ),
                        "confidence": "high",
                        "related_evidence": (
                            f"{file_path}:{state_line}: {source_line}"
                        ),
                    })
                continue

            # 2. ScheduledExecutorService calls — must verify receiver type
            # and the scheduling call itself must intersect changed lines.
            sched_calls = find_method_calls(
                method_node_ref, _SCHEDULING_METHODS, source_bytes,
                receiver_check="ScheduledExecutorService",
            )
            if sched_calls:
                # Verify the scheduling call line is in changed_lines
                call_changed = changed_lines is not None and any(
                    c["start_line"] in changed_lines for c in sched_calls
                )
                if changed_lines is not None and not call_changed:
                    # Scheduling call is pre-existing
                    continue
                candidates.append({
                    "invariant_id": "no-temporary-monitoring",
                    "file": file_path,
                    "start_line": sched_calls[0]["start_line"],
                    "end_line": sched_calls[0]["start_line"],
                    "pattern": "scheduled work",
                    "evidence": (
                        f"Method {method['name']} calls "
                        f"executor.{sched_calls[0]['method']}()"
                    ),
                    "confidence": "high",
                })
                continue

            # 3. Unbounded polling loops with state changes.
            # The loop itself must intersect changed lines.
            unbounded = _find_unbounded_loops(method_node_ref, source_bytes)
            if unbounded:
                for loop_node in unbounded:
                    loop_start = loop_node.start_point[0] + 1
                    # Verify the loop itself intersects changed lines
                    if changed_lines is not None and loop_start not in changed_lines:
                        continue
                    has_sc = has_state_change_in_tree(loop_node, source_bytes)
                    if has_sc:
                        candidates.append({
                            "invariant_id": "no-temporary-monitoring",
                            "file": file_path,
                            "start_line": loop_start,
                            "end_line": loop_node.end_point[0] + 1,
                            "pattern": "state polling",
                            "evidence": (
                                f"Method {method['name']} contains an unbounded "
                                f"polling loop with state-change calls"
                            ),
                            "confidence": "medium",
                        })
                        break

            # 4. Retry loops with sleep/backoff — only flag when
            # the sleeping loop ALSO contains a state-change call
            # within the SAME loop body, AND at least one structural
            # element (loop opening, qualifying sleep/backoff, or
            # state-change child) intersects changed lines.
            # (P1 finding 4: changed-child anchoring)
            sleep_loops = _find_sleep_loops(method_node_ref, source_bytes)
            if sleep_loops:
                for loop_node in sleep_loops:
                    loop_start = loop_node.start_point[0] + 1
                    loop_end = loop_node.end_point[0] + 1
                    has_sc = has_state_change_in_tree(loop_node, source_bytes)
                    if not has_sc:
                        continue
                    sleep_hits = _find_sleep_lines(loop_node, source_bytes)
                    sc_hits = _find_state_change_lines(loop_node, source_bytes)
                    anchor_line = loop_start
                    # Accept when the loop opening itself is changed OR
                    # a qualifying child (sleep/state-change) within the
                    # loop is newly changed. Anchor on that changed child.
                    if changed_lines is not None:
                        qualifying = {loop_start} | sleep_hits | sc_hits
                        changed_qualifying = qualifying & changed_lines
                        if not changed_qualifying:
                            continue
                        anchor_line = min(changed_qualifying)
                    candidates.append({
                        "invariant_id": "no-temporary-monitoring",
                        "file": file_path,
                        "start_line": anchor_line,
                        "end_line": anchor_line,
                        "pattern": "wait retry",
                        "evidence": (
                            f"Method {method['name']} contains sleep/backoff "
                            "with state-change in the same retry loop"
                        ),
                        "confidence": "high",
                        "related_evidence": (
                            f"Enclosing retry loop lines {loop_start}-{loop_end}; "
                            f"sleep lines {sorted(sleep_hits)}; "
                            f"state-change lines {sorted(sc_hits)}"
                        ),
                    })
                    break

    return candidates


def _find_sleep_loops(
    node: tree_sitter.Node, source_bytes: bytes
) -> list[tree_sitter.Node]:
    """Find loops (for, while, do) that contain Thread.sleep or
    TimeUnit.*.sleep calls within their body.

    Returns the loop nodes (not the sleep nodes), so the caller can
    verify that state changes also reside in the same loop.
    """
    results: list[tree_sitter.Node] = []
    for child in node.children:
        if child.type in ("for_statement", "while_statement", "do_statement") and (
            _search_sleep(child, source_bytes, require_loop=False, in_loop=True)
        ):
            results.append(child)
        results.extend(_find_sleep_loops(child, source_bytes))
    return results


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


def _find_sleep_lines(
    node: tree_sitter.Node, source_bytes: bytes
) -> set[int]:
    """Return line numbers of Thread.sleep/TimeUnit.*.sleep calls in *node*."""
    results: set[int] = set()
    for child in node.children:
        if child.type == "method_invocation":
            name_node = child.child_by_field_name("name")
            if name_node is not None and _node_text(name_node, source_bytes) == "sleep":
                obj = child.child_by_field_name("object")
                if obj is not None:
                    obj_text = _node_text(obj, source_bytes)
                    if obj_text == "Thread" or obj_text.startswith("TimeUnit"):
                        results.add(child.start_point[0] + 1)
        results.update(_find_sleep_lines(child, source_bytes))
    return results


def _find_state_change_lines(
    node: tree_sitter.Node, source_bytes: bytes
) -> set[int]:
    """Return line numbers of state-change calls in *node*."""
    results: set[int] = set()
    for child in node.children:
        if child.type == "method_invocation":
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                called = _node_text(name_node, source_bytes)
                if called in _STATE_CHANGE_PATTERNS:
                    results.add(child.start_point[0] + 1)
        results.update(_find_state_change_lines(child, source_bytes))
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _node_text(node: tree_sitter.Node, source_bytes: bytes) -> str:
    """Return the source text spanned by *node*."""
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8")
