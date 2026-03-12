"""Multi-language AST parsing via tree-sitter with a LanguageRouter."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import tree_sitter_python as tspython
import tree_sitter_yaml as tsyaml
from tree_sitter import Language, Parser, Node

from src.models.nodes import (
    DatasetNode,
    FunctionNode,
    Language as LangEnum,
    ModuleNode,
    StorageType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language Router
# ---------------------------------------------------------------------------

_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".sql": "sql",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
}

_LANG_ENUM_MAP: dict[str, LangEnum] = {
    "python": LangEnum.PYTHON,
    "sql": LangEnum.SQL,
    "yaml": LangEnum.YAML,
    "javascript": LangEnum.JAVASCRIPT,
    "typescript": LangEnum.TYPESCRIPT,
}


def _build_languages() -> dict[str, Language]:
    """Build tree-sitter Language objects for each supported grammar."""
    langs: dict[str, Language] = {}
    try:
        langs["python"] = Language(tspython.language())
    except Exception:
        logger.warning("tree-sitter-python grammar unavailable")
    try:
        langs["yaml"] = Language(tsyaml.language())
    except Exception:
        logger.warning("tree-sitter-yaml grammar unavailable")
    return langs


_LANGUAGES: dict[str, Language] = _build_languages()


def language_for_file(path: str | Path) -> Optional[str]:
    """Return the language key for a file path, or None if unsupported."""
    ext = Path(path).suffix.lower()
    return _EXTENSION_MAP.get(ext)


def get_parser(lang_key: str) -> Optional[Parser]:
    """Return a configured Parser for the given language key."""
    lang = _LANGUAGES.get(lang_key)
    if lang is None:
        return None
    parser = Parser(lang)
    return parser


# ---------------------------------------------------------------------------
# Python-specific extraction helpers
# ---------------------------------------------------------------------------


def _text(node: Node) -> str:
    return node.text.decode("utf-8") if node.text else ""


def _extract_python_imports(root: Node) -> list[str]:
    """Walk the AST and collect all import targets."""
    imports: list[str] = []
    for child in root.children:
        if child.type == "import_statement":
            for name_node in child.children:
                if name_node.type == "dotted_name":
                    imports.append(_text(name_node))
        elif child.type == "import_from_statement":
            module_name = ""
            for name_node in child.children:
                if name_node.type == "dotted_name":
                    module_name = _text(name_node)
                    break
                elif name_node.type == "relative_import":
                    module_name = _text(name_node)
                    break
            if module_name:
                imports.append(module_name)
    return imports


def _extract_python_functions(root: Node, module_path: str) -> list[FunctionNode]:
    """Extract top-level and class-level function definitions."""
    functions: list[FunctionNode] = []
    for child in root.children:
        if child.type == "function_definition":
            fn = _parse_function_node(child, module_path)
            if fn:
                functions.append(fn)
        elif child.type == "decorated_definition":
            for sub in child.children:
                if sub.type == "function_definition":
                    fn = _parse_function_node(sub, module_path)
                    if fn:
                        decorators = [
                            _text(d) for d in child.children if d.type == "decorator"
                        ]
                        fn.decorators = decorators
                        functions.append(fn)
        elif child.type == "class_definition":
            class_name = ""
            for sub in child.children:
                if sub.type == "identifier":
                    class_name = _text(sub)
                    break
            body = None
            for sub in child.children:
                if sub.type == "block":
                    body = sub
                    break
            if body:
                for member in body.children:
                    if member.type == "function_definition":
                        fn = _parse_function_node(
                            member, module_path, class_name=class_name
                        )
                        if fn:
                            functions.append(fn)
                    elif member.type == "decorated_definition":
                        for msub in member.children:
                            if msub.type == "function_definition":
                                fn = _parse_function_node(
                                    msub, module_path, class_name=class_name
                                )
                                if fn:
                                    decorators = [
                                        _text(d)
                                        for d in member.children
                                        if d.type == "decorator"
                                    ]
                                    fn.decorators = decorators
                                    functions.append(fn)
    return functions


def _parse_function_node(
    node: Node, module_path: str, class_name: str = ""
) -> Optional[FunctionNode]:
    name = ""
    signature = ""
    docstring = ""
    for child in node.children:
        if child.type == "identifier":
            name = _text(child)
        elif child.type == "parameters":
            signature = _text(child)
        elif child.type == "block":
            first_stmt = child.children[0] if child.children else None
            if first_stmt and first_stmt.type == "expression_statement":
                expr = first_stmt.children[0] if first_stmt.children else None
                if expr and expr.type == "string":
                    docstring = _text(expr).strip("\"'")
    if not name:
        return None
    qualified = f"{class_name}.{name}" if class_name else name
    is_public = not name.startswith("_")
    return FunctionNode(
        qualified_name=qualified,
        parent_module=module_path,
        signature=f"{name}{signature}",
        is_public_api=is_public,
        line_start=node.start_point[0] + 1,
        line_end=node.end_point[0] + 1,
        docstring=docstring,
    )


def _extract_python_classes(root: Node) -> list[str]:
    classes: list[str] = []
    for child in root.children:
        if child.type == "class_definition":
            for sub in child.children:
                if sub.type == "identifier":
                    classes.append(_text(sub))
                    break
        elif child.type == "decorated_definition":
            for sub in child.children:
                if sub.type == "class_definition":
                    for ssub in sub.children:
                        if ssub.type == "identifier":
                            classes.append(_text(ssub))
                            break
    return classes


def _extract_python_decorators(root: Node) -> list[str]:
    decorators: list[str] = []
    for child in root.children:
        if child.type == "decorated_definition":
            for sub in child.children:
                if sub.type == "decorator":
                    decorators.append(_text(sub))
    return decorators


def _extract_python_data_references(root: Node, source_file: str) -> list[DatasetNode]:
    """Detect pandas/PySpark/SQLAlchemy read/write calls and extract dataset refs."""
    datasets: list[DatasetNode] = []
    _walk_for_data_calls(root, source_file, datasets)
    return datasets


_READ_PATTERNS = {
    "read_csv", "read_excel", "read_parquet", "read_json", "read_sql",
    "read_sql_query", "read_sql_table", "read_table", "read_feather",
    "read_orc", "read_fwf",
}
_WRITE_PATTERNS = {
    "to_csv", "to_excel", "to_parquet", "to_json", "to_sql",
    "to_feather", "to_orc",
}
_SPARK_READ = {"load", "csv", "parquet", "json", "orc", "jdbc", "table", "format"}
_SPARK_WRITE = {"save", "saveAsTable", "insertInto"}


def _walk_for_data_calls(node: Node, source_file: str, datasets: list[DatasetNode]):
    """Recursively walk the AST looking for data read/write calls."""
    if node.type == "call":
        func_text = ""
        if node.children:
            func_node = node.children[0]
            func_text = _text(func_node)

        method_name = func_text.rsplit(".", 1)[-1] if "." in func_text else func_text

        is_read = method_name in _READ_PATTERNS
        is_write = method_name in _WRITE_PATTERNS
        is_spark_read = method_name in _SPARK_READ and "read" in func_text.lower()
        is_spark_write = method_name in _SPARK_WRITE and "write" in func_text.lower()

        if is_read or is_write or is_spark_read or is_spark_write:
            arg_str = _extract_first_string_arg(node)
            name = arg_str if arg_str else f"<dynamic:{method_name}>"
            storage = StorageType.FILE
            if "sql" in method_name.lower() or "table" in method_name.lower() or "jdbc" in method_name.lower():
                storage = StorageType.TABLE
            datasets.append(
                DatasetNode(
                    name=name,
                    storage_type=storage,
                    source_file=source_file,
                    line_number=node.start_point[0] + 1,
                )
            )

        if "execute" in method_name.lower() and "engine" in func_text.lower():
            arg_str = _extract_first_string_arg(node)
            datasets.append(
                DatasetNode(
                    name=arg_str or f"<dynamic:sqlalchemy>",
                    storage_type=StorageType.TABLE,
                    source_file=source_file,
                    line_number=node.start_point[0] + 1,
                )
            )

    for child in node.children:
        _walk_for_data_calls(child, source_file, datasets)


def _extract_first_string_arg(call_node: Node) -> str:
    """Extract the first string-literal argument from a call node."""
    for child in call_node.children:
        if child.type == "argument_list":
            for arg in child.children:
                if arg.type == "string":
                    return _text(arg).strip("\"'")
                if arg.type == "concatenated_string":
                    return _text(arg).strip("\"'")
    return ""


# ---------------------------------------------------------------------------
# Complexity estimation
# ---------------------------------------------------------------------------


def _estimate_complexity(root: Node) -> float:
    """Approximate cyclomatic complexity by counting branch nodes."""
    branch_types = {
        "if_statement", "elif_clause", "for_statement", "while_statement",
        "try_statement", "except_clause", "with_statement",
        "conditional_expression", "boolean_operator",
    }
    count = 1
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type in branch_types:
            count += 1
        stack.extend(n.children)
    return float(count)


# ---------------------------------------------------------------------------
# YAML extraction helpers
# ---------------------------------------------------------------------------


def _extract_yaml_keys(root: Node) -> list[str]:
    """Extract top-level keys from a YAML document."""
    keys: list[str] = []
    for child in root.children:
        if child.type == "block_mapping":
            for pair in child.children:
                if pair.type == "block_mapping_pair":
                    key_node = pair.children[0] if pair.children else None
                    if key_node:
                        keys.append(_text(key_node))
        elif child.type == "document":
            keys.extend(_extract_yaml_keys(child))
    return keys


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_module(path: str | Path) -> Optional[ModuleNode]:
    """Parse a file and return a ModuleNode with extracted metadata."""
    path = Path(path)
    if not path.is_file():
        return None

    lang_key = language_for_file(path)
    if lang_key is None:
        return None

    try:
        source = path.read_bytes()
    except Exception as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return None

    source_text = source.decode("utf-8", errors="replace")
    total_lines = source_text.count("\n") + 1
    comment_lines = sum(
        1 for line in source_text.splitlines() if line.strip().startswith("#")
    )
    comment_ratio = comment_lines / max(total_lines, 1)

    if lang_key == "sql":
        return ModuleNode(
            path=str(path),
            language=_LANG_ENUM_MAP.get(lang_key, LangEnum.UNKNOWN),
            lines_of_code=total_lines,
            comment_ratio=comment_ratio,
        )

    parser = get_parser(lang_key)
    if parser is None:
        return ModuleNode(
            path=str(path),
            language=_LANG_ENUM_MAP.get(lang_key, LangEnum.UNKNOWN),
            lines_of_code=total_lines,
            comment_ratio=comment_ratio,
        )

    try:
        tree = parser.parse(source)
    except Exception as exc:
        logger.warning("Parse failed for %s: %s", path, exc)
        return ModuleNode(
            path=str(path),
            language=_LANG_ENUM_MAP.get(lang_key, LangEnum.UNKNOWN),
            lines_of_code=total_lines,
            comment_ratio=comment_ratio,
        )

    root = tree.root_node

    if lang_key == "python":
        imports = _extract_python_imports(root)
        functions = _extract_python_functions(root, str(path))
        classes = _extract_python_classes(root)
        decorators = _extract_python_decorators(root)
        complexity = _estimate_complexity(root)
        docstring = ""
        if root.children:
            first = root.children[0]
            if first.type == "expression_statement" and first.children:
                expr = first.children[0]
                if expr.type == "string":
                    docstring = _text(expr).strip("\"'")

        return ModuleNode(
            path=str(path),
            language=LangEnum.PYTHON,
            lines_of_code=total_lines,
            comment_ratio=comment_ratio,
            imports=imports,
            public_functions=[f.qualified_name for f in functions if f.is_public_api],
            classes=classes,
            decorators=decorators,
            complexity_score=complexity,
            docstring=docstring,
        )

    if lang_key == "yaml":
        keys = _extract_yaml_keys(root)
        return ModuleNode(
            path=str(path),
            language=LangEnum.YAML,
            lines_of_code=total_lines,
            comment_ratio=comment_ratio,
            public_functions=keys,
        )

    return ModuleNode(
        path=str(path),
        language=_LANG_ENUM_MAP.get(lang_key, LangEnum.UNKNOWN),
        lines_of_code=total_lines,
        comment_ratio=comment_ratio,
    )


def extract_functions(path: str | Path) -> list[FunctionNode]:
    """Extract all function definitions from a Python file."""
    path = Path(path)
    lang_key = language_for_file(path)
    if lang_key != "python":
        return []
    parser = get_parser("python")
    if parser is None:
        return []
    try:
        source = path.read_bytes()
        tree = parser.parse(source)
        return _extract_python_functions(tree.root_node, str(path))
    except Exception as exc:
        logger.warning("Function extraction failed for %s: %s", path, exc)
        return []


def extract_data_references(path: str | Path) -> list[DatasetNode]:
    """Detect pandas/PySpark/SQLAlchemy data read/write calls in a Python file."""
    path = Path(path)
    lang_key = language_for_file(path)
    if lang_key != "python":
        return []
    parser = get_parser("python")
    if parser is None:
        return []
    try:
        source = path.read_bytes()
        tree = parser.parse(source)
        return _extract_python_data_references(tree.root_node, str(path))
    except Exception as exc:
        logger.warning("Data reference extraction failed for %s: %s", path, exc)
        return []
