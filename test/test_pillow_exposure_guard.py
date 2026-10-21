"""Conservative source guard requiring Pillow risk reassessment in the CI test job.

This detects selected Python syntax, not global reachability or arbitrary dynamic
dispatch. See security/pillow-review-2026-10-21.md for the scope and limitations.
"""

import ast
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
IMAGE_APIS = {"image", "file_uploader", "camera_input", "logo", "pyplot"}


def production_modules(root):
    """Include entry points, engine, scripts and new Python packages/helpers."""
    for directory, children, files in os.walk(root):
        children[:] = sorted(
            name for name in children if not name.startswith(".") and name not in {"test", "tests", "docs", "autoloop", "node_modules"}
        )
        for name in sorted(files):
            if name.endswith(".py"):
                yield Path(directory) / name


def image_exposures(source):
    tree = ast.parse(source)
    bindings = {}
    issues = []

    def bind(target, value):
        if isinstance(target, ast.Name):
            bindings.setdefault(target.id, value)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                bind(element, value)

    # Resolve imports, simple callable aliases, container assignments and `with`
    # targets without executing production code. Imports take precedence so a
    # later rebinding does not silently erase an API from the guard.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bindings[alias.asname or alias.name.split(".")[0]] = alias.name if alias.asname else alias.name.split(".")[0]
                if alias.name.split(".")[0] == "PIL":
                    issues.append((node.lineno, "Pillow import/operations require reassessment"))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                bindings[alias.asname or alias.name] = f"{module}.{alias.name}"
            if module.split(".")[0] == "PIL":
                issues.append((node.lineno, "Pillow import/operations require reassessment"))
            if module.startswith("streamlit") and any(alias.name == "*" for alias in node.names):
                issues.append((node.lineno, "Streamlit wildcard import hides image API bindings"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                bind(target, node.value)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            bind(node.target, node.value)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    bind(item.optional_vars, item.context_expr)

    def qualified(node, seen=frozenset()):
        if isinstance(node, ast.Name):
            if node.id in seen:
                return ""
            value = bindings.get(node.id, "")
            return value if isinstance(value, str) else qualified(value, seen | {node.id})
        if isinstance(node, ast.Attribute):
            return f"{qualified(node.value, seen)}.{node.attr}"
        if isinstance(node, ast.Call):
            return qualified(node.func, seen)
        if isinstance(node, ast.Subscript):
            return qualified(node.value, seen)
        return ""

    def argument(call, name, position=None):
        for keyword in call.keywords:
            if keyword.arg == name:
                return keyword.value
        return call.args[position] if position is not None and len(call.args) > position else None

    def absent_or_literal(node, safe_values):
        return node is None or isinstance(node, ast.Constant) and node.value in safe_values

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = qualified(node.func)
        if not name.startswith("streamlit."):
            continue
        api = name.rsplit(".", 1)[-1]
        risky = api in IMAGE_APIS
        if api == "set_page_config":
            risky = not absent_or_literal(argument(node, "page_icon", 1), (None, "random"))
        elif api == "chat_message":
            risky = not absent_or_literal(argument(node, "avatar", 1), (None, "user", "assistant"))
        elif api == "chat_input":
            risky = not absent_or_literal(argument(node, "accept_file"), (None, False))
        if api in {"set_page_config", "chat_message", "chat_input"} and (
            any(keyword.arg is None for keyword in node.keywords) or any(isinstance(arg, ast.Starred) for arg in node.args)
        ):
            risky = True  # Expanded arguments could supply image-related values.
        if risky:
            issues.append((node.lineno, f"{name} requires image-path reassessment"))
    return sorted(set(issues))


def test_production_image_paths_require_reassessment_while_pillow_exceptions_configured():
    exceptions = json.loads((ROOT / "security/pip-audit-ignores.json").read_text())
    if not any(entry["package"] == "pillow" for entry in exceptions.values()):
        pytest.skip("Pillow exceptions removed; this temporary exposure policy no longer applies")
    modules = list(production_modules(ROOT))
    assert {ROOT / name for name in ("app.py", "api.py", "cli.py", "engine/service.py")} <= set(modules)
    issues = [f"{path.relative_to(ROOT)}:{line}: {reason}" for path in modules for line, reason in image_exposures(path.read_text())]
    assert not issues, "Reassess/remove Pillow exceptions before accepting image-processing pathways:\n" + "\n".join(issues)


@pytest.mark.parametrize(
    "source",
    [
        "import streamlit as ui; ui.image(data)",
        "from streamlit import image as show; show(data)",
        "import streamlit as st; st.sidebar.image(data)",
        "import streamlit as st; cols = st.columns(2); cols[0].image(data)",
        "import streamlit as st; left, right = st.columns(2); right.image(data)",
        "import streamlit as st\nwith st.container() as panel:\n panel.image(data)",
        "import streamlit as st; show = st.image; show(data)",
        "import streamlit as st; st.file_uploader('Image')",
        "from streamlit import camera_input as camera; camera('Camera')",
        "import streamlit as st; st.logo(path)",
        "import streamlit as st; st.set_page_config(page_icon='icon.png')",
        "import streamlit as st; st.set_page_config('Title', icon)",
        "import streamlit as st; st.set_page_config(**settings)",
        "import streamlit as st; st.set_page_config(*settings)",
        "import streamlit as st; st.chat_message('assistant', avatar=path)",
        "import streamlit as st; st.chat_message('assistant', **settings)",
        "import streamlit as st; st.chat_input('Message', accept_file=True)",
        "import streamlit as st; st.chat_input(**settings)",
        "import streamlit as st; st.pyplot(figure)",
        "from PIL import Image as Picture; Picture.open(path)",
        "import PIL.Image as picture; picture.new('RGB', (1, 1))",
        "from PIL import ImageMorph; ImageMorph.MorphOp().apply(image)",
        "from streamlit import *\nimage(data)",
    ],
)
def test_guard_detects_executable_image_entry_points(source):
    assert image_exposures(source)


@pytest.mark.parametrize(
    "source",
    [
        "# st.image(data); from PIL import Image\ntext = 'st.file_uploader() PIL.Image.open()'",
        "import streamlit as st; st.write('st.image(data)'); st.text('PIL.Image.open(path)')",
        "import streamlit as st; st.set_page_config(page_title='Demo', layout='wide')",
        "import streamlit as st; st.set_page_config(page_icon=None)",
        "import streamlit as st; st.set_page_config(page_icon='random')",
        "import streamlit as st; st.chat_message('assistant'); st.chat_message('user', avatar='user')",
        "import streamlit as st; st.chat_input('Text', accept_file=False)",
        "import streamlit as st; st.button('Go', icon=':material/arrow_forward:')",
        "other.image(data)",
    ],
)
def test_guard_ignores_comments_strings_and_text_only_apis(source):
    assert not image_exposures(source)


def test_module_discovery_includes_helpers_and_nested_packages(tmp_path):
    for name in ("app.py", "api.py", "engine/images.py", "new_package/nested/preview.py", "test/fixture.py", ".venv/image.py"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("import streamlit as ui; ui.image(data)")
    modules = list(production_modules(tmp_path))
    assert {path.relative_to(tmp_path).as_posix() for path in modules} == {
        "app.py",
        "api.py",
        "engine/images.py",
        "new_package/nested/preview.py",
    }
    assert all(image_exposures(path.read_text()) for path in modules)
