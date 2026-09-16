"""Tests for scripts/setup-selfhost.py (chunk A: CLI + prerequisites)."""

from __future__ import annotations

import http.client
import importlib.util
import sys
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "setup_selfhost", SCRIPTS_DIR / "setup-selfhost.py"
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod  # dataclasses resolve types via sys.modules
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------


def test_parse_args_defaults() -> None:
    config = _mod.parse_args([])
    assert not config.dry_run
    assert not config.check_only
    assert not config.force


def test_parse_args_flags() -> None:
    config = _mod.parse_args(["--dry-run", "--check", "--force"])
    assert config.dry_run
    assert config.check_only
    assert config.force


# ---------------------------------------------------------------------------
# prerequisites
# ---------------------------------------------------------------------------


def test_check_tool_found() -> None:
    with mock.patch.object(_mod.shutil, "which", return_value="/x"):
        result = _mod.check_tool("npm")
    assert result.ok


def test_check_tool_missing_has_hint() -> None:
    with mock.patch.object(_mod.shutil, "which", return_value=None):
        result = _mod.check_tool("npm")
    assert not result.ok
    assert "nodejs.org" in result.hint


def test_check_tool_missing_never_leaks() -> None:
    with mock.patch.object(_mod.shutil, "which", return_value=None):
        result = _mod.check_tool("openssl")
    assert "secret" not in result.hint.lower()


def test_check_python_version_current() -> None:
    assert _mod.check_python_version().ok


def test_report_all_ok() -> None:
    results = [
        _mod.PrereqResult(name="python", ok=True),
        _mod.PrereqResult(name="npm", ok=True),
    ]
    assert _mod.report_prerequisites(results)


def test_report_failure() -> None:
    results = [
        _mod.PrereqResult(name="python", ok=True),
        _mod.PrereqResult(name="npm", ok=False, hint="install it"),
    ]
    assert not _mod.report_prerequisites(results)


# ---------------------------------------------------------------------------
# Spotify credentials (chunk B)
# ---------------------------------------------------------------------------


def _fake_token_response(payload: dict[str, object]) -> mock.MagicMock:
    response = mock.MagicMock()
    response.read.return_value = __import__("json").dumps(payload).encode()
    response.__enter__.return_value = response
    return response


def test_prompt_client_id_accepts_valid() -> None:
    with mock.patch("builtins.input", return_value="a" * 32):
        assert _mod.prompt_client_id() == "a" * 32


def test_prompt_client_id_rejects_then_accepts(capsys: object) -> None:
    inputs = iter(["nope", "b" * 32])
    with mock.patch("builtins.input", side_effect=lambda _: next(inputs)):
        assert _mod.prompt_client_id() == "b" * 32
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "doesn't look like" in out


def test_prompt_client_secret_hidden() -> None:
    with mock.patch.object(_mod.getpass, "getpass", return_value="s3cret"):
        assert _mod.prompt_client_secret() == "s3cret"


def test_validate_credentials_ok() -> None:
    with mock.patch.object(
        _mod.urllib.request, "urlopen",
        return_value=_fake_token_response({"access_token": "tok"}),
    ):
        ok, message = _mod.validate_spotify_credentials("a" * 32, "secret")
    assert ok
    assert "secret" not in message


def test_validate_credentials_rejected() -> None:
    import urllib.error

    error = urllib.error.HTTPError(
        "https://x", 401, "Unauthorized", http.client.HTTPMessage(), None
    )
    with mock.patch.object(
        _mod.urllib.request, "urlopen", side_effect=error
    ):
        ok, message = _mod.validate_spotify_credentials("a" * 32, "bad")
    assert not ok
    assert "bad" not in message


def test_validate_credentials_bad_request() -> None:
    import urllib.error

    error = urllib.error.HTTPError(
        "https://x", 400, "Bad Request", http.client.HTTPMessage(), None
    )
    with mock.patch.object(
        _mod.urllib.request, "urlopen", side_effect=error
    ):
        ok, message = _mod.validate_spotify_credentials("a" * 32, "bad")
    assert not ok
    assert "bad request body" in message


def test_validate_credentials_unreachable() -> None:
    import urllib.error

    with mock.patch.object(
        _mod.urllib.request,
        "urlopen",
        side_effect=urllib.error.URLError("down"),
    ):
        ok, _ = _mod.validate_spotify_credentials("a" * 32, "secret")
    assert not ok


def test_generate_jwt_secret_format() -> None:
    first = _mod.generate_jwt_secret()
    second = _mod.generate_jwt_secret()
    assert len(first) == 64
    assert first != second


def test_build_dev_vars_content_keys() -> None:
    content = _mod.build_dev_vars_content("id", "sec", "jwt")
    assert 'SPOTIFY_CLIENT_ID="id"' in content
    assert 'SPOTIFY_CLIENT_SECRET="sec"' in content
    assert 'JWT_SECRET="jwt"' in content


def test_write_dev_vars_dry_run_writes_nothing(
    tmp_path: object, capsys: object
) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    target = tmp_path / ".dev.vars"  # type: ignore[operator]
    assert _mod.write_dev_vars(
        target, "id", "TOPSECRET", "jwt", dry_run=True
    )
    assert not target.exists()
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "TOPSECRET" not in out


def test_write_dev_vars_refuses_overwrite(
    tmp_path: object, capsys: object
) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    target = tmp_path / ".dev.vars"  # type: ignore[operator]
    target.write_text("existing")
    assert not _mod.write_dev_vars(target, "id", "sec", "jwt")
    assert target.read_text() == "existing"
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "sec" not in out


def test_write_dev_vars_force(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    target = tmp_path / ".dev.vars"  # type: ignore[operator]
    target.write_text("existing")
    assert _mod.write_dev_vars(target, "id", "sec", "jwt", force=True)
    assert "SPOTIFY_CLIENT_ID" in target.read_text()


# ---------------------------------------------------------------------------
# Cloudflare path (chunk C)
# ---------------------------------------------------------------------------


SAMPLE_TOML = """\
name = "x"

[vars]
ALLOWED_REDIRECT_URIS = "https://app.spotibye.com"

[[kv_namespaces]]
binding = "CACHE_KV"
id = "oldid1"
preview_id = "oldprev1"

[[kv_namespaces]]
binding = "SESSIONS_KV"
id = "oldid2"
preview_id = "oldprev2"

[env.production]
vars = { ALLOWED_REDIRECT_URIS = "https://app.spotibye.com" }

[[env.production.kv_namespaces]]
binding = "CACHE_KV"
id = "oldid1"
preview_id = "oldprev1"
"""


def test_patch_kv_ids_all_blocks() -> None:
    ids = {"CACHE_KV": ("new1", "newp1"), "SESSIONS_KV": ("new2", "newp2")}
    out = _mod.patch_kv_ids(SAMPLE_TOML, ids)
    assert out.count('"new1"') == 2
    assert out.count('"newp1"') == 2
    assert out.count('"new2"') == 1
    assert "oldid1" not in out
    assert "oldprev2" not in out
    assert 'binding = "CACHE_KV"' in out


def test_patch_kv_ids_unknown_binding_untouched() -> None:
    out = _mod.patch_kv_ids(SAMPLE_TOML, {"NOPE": ("a", "b")})
    assert out == SAMPLE_TOML


def test_patch_kv_ids_leaves_non_kv_sections() -> None:
    text = """\
# ALLOWED_REDIRECT_URIS = "commented"
# KV Namespaces
[[kv_namespaces]]
binding = "CACHE_KV"
id = "old"
preview_id = "oldprev"

[[queues.producers]]
binding = "ANALYSIS_QUEUE"
queue = "spotibye-analysis"

[[queues.consumers]]
queue = "spotibye-analysis"
dead_letter_queue = "spotibye-analysis-dlq"

[[durable_objects.bindings]]
name = "ANALYSIS_STATUS"

[[migrations]]
tag = "v1"
"""
    out = _mod.patch_kv_ids(text, {"CACHE_KV": ("n", "np")})
    assert '"n"' in out and '"np"' in out
    assert '"spotibye-analysis"' in out
    assert '"spotibye-analysis-dlq"' in out
    assert '"ANALYSIS_STATUS"' in out
    assert 'tag = "v1"' in out
    assert "# KV Namespaces" in out


def test_patch_allowlist_replaces_all() -> None:
    out = _mod.patch_allowlist(SAMPLE_TOML, "http://127.0.0.1:8080/callback")
    assert "app.spotibye.com" not in out
    assert out.count("http://127.0.0.1:8080/callback") == 2


def test_patch_allowlist_skips_comments() -> None:
    text = '# ALLOWED_REDIRECT_URIS = "old"\nALLOWED_REDIRECT_URIS = "old"\n'
    out = _mod.patch_allowlist(text, "new")
    assert '# ALLOWED_REDIRECT_URIS = "old"' in out
    assert 'ALLOWED_REDIRECT_URIS = "new"' in out


def test_patch_allowlist_ignores_prefixed_names() -> None:
    text = 'MY_ALLOWED_REDIRECT_URIS = "keep"\nALLOWED_REDIRECT_URIS = "old"\n'
    out = _mod.patch_allowlist(text, "new")
    assert 'MY_ALLOWED_REDIRECT_URIS = "keep"' in out
    assert 'ALLOWED_REDIRECT_URIS = "new"' in out


def test_patch_allowlist_backslash_uri_safe() -> None:
    out = _mod.patch_allowlist('ALLOWED_REDIRECT_URIS = "old"', "C:\\x\\1")
    assert out == 'ALLOWED_REDIRECT_URIS = "C:\\x\\1"\n'


def test_generate_selfhost_config_dry_run(tmp_path: Path) -> None:
    target = tmp_path / "wrangler.selfhost.toml"
    assert _mod.generate_selfhost_config(
        Path("x"), target, {}, "http://127.0.0.1:8080/callback", dry_run=True
    )
    assert not target.exists()


def test_generate_selfhost_config_writes(tmp_path: Path) -> None:
    template = tmp_path / "wrangler.toml"
    template.write_text(SAMPLE_TOML)
    target = tmp_path / "wrangler.selfhost.toml"
    ids = {"CACHE_KV": ("n1", "np1"), "SESSIONS_KV": ("n2", "np2")}
    assert _mod.generate_selfhost_config(
        template, target, ids, "http://127.0.0.1:8080/callback"
    )
    text = target.read_text()
    assert '"n1"' in text and "oldid1" not in text
    assert "http://127.0.0.1:8080/callback" in text
    assert "app.spotibye.com" not in text


def test_generate_selfhost_config_refuses_overwrite(tmp_path: Path) -> None:
    template = tmp_path / "wrangler.toml"
    template.write_text(SAMPLE_TOML)
    target = tmp_path / "wrangler.selfhost.toml"
    target.write_text("existing")
    assert not _mod.generate_selfhost_config(template, target, {}, "u")
    assert target.read_text() == "existing"


def test_provision_kv_parses_id() -> None:
    with mock.patch.object(
        _mod, "run_wrangler", return_value=(True, 'id = "abcdef1234567890ABCDEF1234567890"')
    ):
        ok, value = _mod.provision_kv_namespace("CACHE_KV")
    assert ok
    assert value == "abcdef1234567890ABCDEF1234567890"


def test_provision_kv_parses_preview_id() -> None:
    with mock.patch.object(
        _mod, "run_wrangler", return_value=(True, 'preview_id = "1234567890abcdef1234567890ABCDEF"')
    ):
        ok, value = _mod.provision_kv_namespace("CACHE_KV", preview=True)
    assert ok
    assert value == "1234567890abcdef1234567890ABCDEF"


def test_provision_kv_ignores_noise() -> None:
    with mock.patch.object(
        _mod, "run_wrangler",
        return_value=(True, "trace abcdef1234567890abcdef1234567890\nno assignment here"),
    ):
        ok, _ = _mod.provision_kv_namespace("CACHE_KV")
    assert not ok


def test_provision_kv_failure() -> None:
    with mock.patch.object(
        _mod, "run_wrangler", return_value=(False, "boom")
    ):
        ok, _ = _mod.provision_kv_namespace("CACHE_KV")
    assert not ok


def test_create_queue_exists_counts_as_success() -> None:
    with mock.patch.object(
        _mod, "run_wrangler", return_value=(False, "Queue already exists")
    ):
        ok, _ = _mod.create_queue("q")
    assert ok


def test_upload_secret_pipes_via_stdin(capsys: object) -> None:
    seen_cmd: list[str] = []
    seen_kwargs: dict[str, object] = {}

    def fake_run(  # type: ignore[no-untyped-def]
        cmd, **kwargs
    ):
        seen_cmd.extend(cmd)
        seen_kwargs.update(kwargs)

        class P:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return P()

    with mock.patch.object(_mod.subprocess, "run", side_effect=fake_run):
        assert _mod.upload_secret("K", "TOPSECRET", "production", "c.toml")
    assert "TOPSECRET" not in " ".join(seen_cmd)
    assert seen_kwargs["input"] == b"TOPSECRET"
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "TOPSECRET" not in out


def test_upload_secret_dry_run(capsys: object) -> None:
    assert _mod.upload_secret("K", "TOPSECRET", "production", "c", dry_run=True)
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "TOPSECRET" not in out


# ---------------------------------------------------------------------------
# portals and probes
# ---------------------------------------------------------------------------


def test_open_portal_dry_run_does_not_open_browser() -> None:
    with mock.patch.object(_mod.webbrowser, "open") as opener:
        _mod.open_portal("https://example.com", dry_run=True)
    opener.assert_not_called()


def test_run_step_success() -> None:
    ok, _ = _mod.run_step([sys.executable, "-c", "print('hi')"])
    assert ok


def test_run_step_failure() -> None:
    ok, _ = _mod.run_step([sys.executable, "-c", "import sys; sys.exit(3)"])
    assert not ok
