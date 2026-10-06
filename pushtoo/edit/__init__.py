"""The profile editor (PRD F10): `pushtoo edit` serves a page on this machine only.

It runs as its own process, never inside the instrument, so it can't touch MIDI
timing (ADR 0001). It never writes your profile: what you change goes in
`<name>-user.yaml` beside it (see profiles/loader.py), which the running Pushtoo
picks up within a second, like any edit.
"""

import json
import logging
import os
import re
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml

from pushtoo.profiles.loader import (
    ProfileError,
    default_config_dir,
    ensure_default,
    load,
    override_path,
    parse,
    profile_paths,
)
from pushtoo.profiles.schema import Profile
from pushtoo.theme import CONTROL_COLOR_NAMES, DEFAULT_THEME

HOST = "127.0.0.1"
EDITS = "edits"  # the source name for errors in the page's own changes
MAX_BODY = 1 << 20

log = logging.getLogger(__name__)


def diff(base: object, edited: object) -> object | None:
    """What `edited` changes from `base`, as an override: maps keep only the keys that
    differ, anything else is all or nothing. None means no change."""
    if isinstance(base, dict) and isinstance(edited, dict):
        changed = {}
        for key, value in edited.items():
            if key not in base:
                changed[key] = value
            elif (d := diff(base[key], value)) is not None:
                changed[key] = d
        return changed or None
    return None if base == edited else edited


class Editor:
    """The profiles folder, as the page sees it. Pure enough to test without HTTP."""

    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir
        ensure_default(config_dir)

    def _path(self, file: str) -> Path:
        """A profile by file name; only files listed in the folder, so a request can't
        reach anything else."""
        for path in profile_paths(self.config_dir):
            if path.name == file:
                return path
        raise ProfileError(f"{file}: no such profile")

    def profiles(self) -> list[dict]:
        found = []
        for path in profile_paths(self.config_dir):
            try:
                name = load(path).name
            except ProfileError:
                name = path.stem
            found.append({"file": path.name, "name": name, "edited": override_path(path).exists()})
        return found

    def _base(self, path: Path) -> dict:
        """The profile as its own file has it, with every default filled in."""
        return parse(path.read_text(), path.name).model_dump(mode="json")

    def profile(self, file: str) -> dict:
        path = self._path(file)
        edits = override_path(path)
        result: dict = {
            "file": path.name,
            "edits_file": edits.name,
            "schema": Profile.model_json_schema(),
            "colors": {
                name: "#{:02x}{:02x}{:02x}".format(*DEFAULT_THEME[name])
                for name in CONTROL_COLOR_NAMES
            },
            "error": None,
        }
        try:
            result["base"] = self._base(path)
        except ProfileError as error:  # the page can't help until the file itself loads
            result |= {"base": None, "profile": None, "error": str(error)}
            return result
        try:
            result["profile"] = load(path).model_dump(mode="json")
        except ProfileError as error:  # broken edits: start again from the file
            result |= {"profile": result["base"], "error": str(error)}
        return result

    def _edits(self, path: Path, edited: dict) -> tuple[object | None, str]:
        """The override for `edited`, and its YAML, checked as Pushtoo will load it."""
        changes = diff(self._base(path), edited)
        text = "" if changes is None else yaml.safe_dump(changes, sort_keys=False)
        try:
            parse(path.read_text(), path.name, text, EDITS)
        except ProfileError as error:
            # A line in edits not yet saved means nothing to you; the field does.
            raise ProfileError(re.sub(rf"^{EDITS}( line \d+)?: ", "", str(error))) from error
        return changes, text

    def validate(self, file: str, edited: dict) -> dict:
        try:
            changes, _ = self._edits(self._path(file), edited)
        except ProfileError as error:
            return {"ok": False, "error": str(error)}
        return {"ok": True, "changes": changes}

    def save(self, file: str, edited: dict) -> dict:
        path = self._path(file)
        try:
            changes, text = self._edits(path, edited)
        except ProfileError as error:
            return {"ok": False, "error": str(error)}
        target = override_path(path)
        if changes is None:
            target.unlink(missing_ok=True)  # back to the file as written
            return {"ok": True, "changes": None, "saved": None}
        header = (
            f"# Edits to {path.name} from `pushtoo edit`. Pushtoo reads them over that file;\n"
            "# delete this file to go back to it as written.\n"
        )
        tmp = target.with_suffix(".tmp")
        tmp.write_text(header + text)
        tmp.replace(target)
        return {"ok": True, "changes": changes, "saved": target.name}


def _handler(editor: Editor, page: bytes, port_holder: list[int]):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args) -> None:
            log.debug(format, *args)

        def _local(self) -> bool:
            """Only this machine's browser: the Host must be ours (no DNS rebinding),
            and a POST must come from our own page."""
            port = port_holder[0]
            hosts = {f"{HOST}:{port}", f"localhost:{port}"}
            if self.headers.get("Host") not in hosts:
                return False
            origin = self.headers.get("Origin")
            return origin is None or origin in {f"http://{h}" for h in hosts}

        def _send(self, status: int, body: bytes, kind: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data: object, status: int = HTTPStatus.OK) -> None:
            self._send(status, json.dumps(data).encode(), "application/json")

        def do_GET(self) -> None:
            if not self._local():
                return self._json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
            url = urlparse(self.path)
            if url.path == "/":
                return self._send(HTTPStatus.OK, page, "text/html; charset=utf-8")
            if url.path == "/api/profiles":
                return self._json(editor.profiles())
            if url.path == "/api/profile":
                file = parse_qs(url.query).get("file", [""])[0]
                try:
                    return self._json(editor.profile(file))
                except ProfileError as error:
                    return self._json({"error": str(error)}, HTTPStatus.NOT_FOUND)
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            if not self._local() or self.headers.get("Content-Type") != "application/json":
                return self._json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self._json({"error": "too large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            try:
                body = json.loads(self.rfile.read(length))
                file, edited = body["file"], body["profile"]
                assert isinstance(file, str) and isinstance(edited, dict)
            except (ValueError, KeyError, AssertionError, TypeError):
                return self._json({"error": "bad request"}, HTTPStatus.BAD_REQUEST)
            action = {"/api/validate": editor.validate, "/api/save": editor.save}.get(self.path)
            if action is None:
                return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            try:
                self._json(action(file, edited))
            except ProfileError as error:
                self._json({"ok": False, "error": str(error)}, HTTPStatus.NOT_FOUND)

    return Handler


def serve(config_dir: Path, port: int = 0) -> ThreadingHTTPServer:
    """A server for the editor on this machine only; port 0 picks a free one."""
    editor = Editor(config_dir)
    page = (resources.files("pushtoo.edit") / "index.html").read_bytes()
    port_holder = [port]
    server = ThreadingHTTPServer((HOST, port), _handler(editor, page, port_holder))
    port_holder[0] = server.server_address[1]
    return server


def main(profile: str | None = None, port: int = 0, open_browser: bool = True) -> int:
    server = serve(default_config_dir(), port)
    url = f"http://{HOST}:{server.server_address[1]}/"
    if profile:
        url += "#" + profile if profile.endswith((".yaml", ".yml")) else f"#{profile}.yaml"
    print(f"Pushtoo profile editor: {url}\nCtrl+C to stop.", flush=True)
    if open_browser and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
