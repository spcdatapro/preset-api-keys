"""Cheap checks that catch the usual UI slips without a browser (the real check is the browser run)."""

import re
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
HTML = (PLUGIN_DIR / "webui" / "main.html").read_text(encoding="utf-8")
STORE = (PLUGIN_DIR / "webui" / "pak-store.js").read_text(encoding="utf-8")
ENTRY = next((PLUGIN_DIR / "extensions" / "webui" / "sidebar-quick-actions-dropdown-start").glob("*.html"))


def store_members() -> set[str]:
    """Top-level members of the store model: methods and properties."""
    model = STORE[STORE.index("const model = {"): STORE.index("export const store")]
    return set(re.findall(r"^  (?:async )?(\w+)\s*(?:\(|:)", model, re.MULTILINE))


def method_body(name: str) -> str:
    body = STORE[STORE.index(f"  {name}("):]
    return body[: body.index("\n  },")]


def test_every_store_member_used_by_the_html_exists():
    used = set(re.findall(r"\bm\.(\w+)", HTML))
    assert used, "the template should use the store"
    assert used <= store_members(), sorted(used - store_members())


def test_the_html_binds_the_store_it_imports():
    assert 'createStore("presetApiKeys"' in STORE
    assert "$store.presetApiKeys" in HTML
    assert "/plugins/preset_api_keys/webui/pak-store.js" in HTML


def test_every_api_call_names_an_existing_handler():
    called = set(re.findall(r'api\("(\w+)"', STORE))
    assert called == {p.stem for p in (PLUGIN_DIR / "api").glob("*.py")}


def test_no_raw_html_rendering_in_the_template():
    assert "x-html" not in HTML and "innerHTML" not in HTML


def test_ids_and_classes_use_the_plugin_prefix():
    static = r'(?<![:\w-]){}="([^"]+)"'  # skips bound attributes such as :class and :id
    names = re.findall(static.format("id"), HTML)
    names += [c for group in re.findall(static.format("class"), HTML) for c in group.split()]
    foreign = {n for n in names if not n.startswith("pak-") and n not in {"button", "confirm", "cancel"}}
    assert not foreign, sorted(foreign)


def test_the_key_field_is_a_password_input_the_browser_should_not_remember():
    field = re.search(r'<input[^>]*id="pak-key"[^>]*>', HTML, re.DOTALL).group(0)
    assert 'type="password"' in field and 'autocomplete="new-password"' in field
    assert HTML.count("<input") == 1


def test_a_typed_key_is_dropped_after_saving_failing_or_closing():
    assert "this.cancelEdit()" in method_body("cleanup")
    save = method_body("async save")
    assert "this.cancelEdit()" in save and 'this.form.key = ""' in save
    assert 'key: ""' in method_body("cancelEdit")


def test_the_store_never_logs_or_keeps_a_key_elsewhere():
    assert "console." not in STORE and "localStorage" not in STORE and "sessionStorage" not in STORE
    for name in ("toastSuccess", "toastError"):
        for call in re.findall(name + r"\(([^;]*)\);", STORE):
            assert "form.key" not in call


def test_strings_built_as_html_escape_everything_dynamic():
    """Confirm dialogs render HTML: dynamic pieces must go through esc()."""
    body = method_body("async remove")
    dialog = body[body.index("showConfirmDialog"): body.index("if (!confirmed)")]
    placeholders = re.findall(r"\$\{([^}]+)\}", dialog)
    assert placeholders and all(p.startswith("esc(") for p in placeholders)


def test_the_menu_entry_opens_this_plugins_modal():
    text = ENTRY.read_text(encoding="utf-8")
    assert "/plugins/preset_api_keys/webui/main.html" in text
    assert 'id="preset-api-keys-dropdown"' in text
