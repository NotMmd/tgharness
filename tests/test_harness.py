import asyncio
import json
import sys
import tempfile
import types as pytypes
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch
from enum import Enum
from pathlib import Path


class DummyClient:
    pass


pyrogram = pytypes.ModuleType("pyrogram")
pyrogram.__path__ = []
pyrogram.Client = DummyClient
sys.modules.setdefault("pyrogram", pyrogram)

pyrogram_enums = pytypes.ModuleType("pyrogram.enums")


class ParseMode(Enum):
    MARKDOWN = "markdown"


class MessagesFilter(Enum):
    PHOTO = "photo"


pyrogram_enums.ParseMode = ParseMode
pyrogram_enums.MessagesFilter = MessagesFilter
sys.modules.setdefault("pyrogram.enums", pyrogram_enums)
pyrogram.enums = pyrogram_enums

pyrogram_types = pytypes.ModuleType("pyrogram.types")


class InlineKeyboardButton:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class InlineKeyboardMarkup:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


pyrogram_types.InlineKeyboardButton = InlineKeyboardButton
pyrogram_types.InlineKeyboardMarkup = InlineKeyboardMarkup
sys.modules.setdefault("pyrogram.types", pyrogram_types)
pyrogram.types = pyrogram_types

pyrogram_filters = pytypes.ModuleType("pyrogram.filters")
sys.modules.setdefault("pyrogram.filters", pyrogram_filters)
pyrogram.filters = pyrogram_filters

pyrogram_handlers = pytypes.ModuleType("pyrogram.handlers")
sys.modules.setdefault("pyrogram.handlers", pyrogram_handlers)
pyrogram.handlers = pyrogram_handlers

pyrogram_raw = pytypes.ModuleType("pyrogram.raw")
pyrogram_raw.__path__ = []
sys.modules.setdefault("pyrogram.raw", pyrogram_raw)
pyrogram.raw = pyrogram_raw

pyrogram_raw_types = pytypes.ModuleType("pyrogram.raw.types")


class InputPeerSelf:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


pyrogram_raw_types.InputPeerSelf = InputPeerSelf
sys.modules.setdefault("pyrogram.raw.types", pyrogram_raw_types)
pyrogram_raw.types = pyrogram_raw_types

pyrogram_raw_functions = pytypes.ModuleType("pyrogram.raw.functions")
messages = pytypes.SimpleNamespace()


class GetHistory:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


messages.GetHistory = GetHistory
pyrogram_raw_functions.messages = messages
sys.modules.setdefault("pyrogram.raw.functions", pyrogram_raw_functions)
pyrogram_raw.functions = pyrogram_raw_functions

pyrogram_errors = pytypes.ModuleType("pyrogram.errors")


class FloodWait(Exception):
    def __init__(self, value):
        self.value = value
        super().__init__(str(value))


class SessionPasswordNeeded(Exception):
    pass


pyrogram_errors.FloodWait = FloodWait
pyrogram_errors.SessionPasswordNeeded = SessionPasswordNeeded
sys.modules.setdefault("pyrogram.errors", pyrogram_errors)


from tgharness.cli import _command_args, build_parser
from tgharness.core import auth
from tgharness.core.accounts import account_identity
from tgharness.core.auth import write_config
from tgharness.core.config import Config
from tgharness.core.gateway import (
    call_client_method,
    decode_value,
    dispatch,
    execute_python,
    invoke_raw,
)
from tgharness.core.ipc import HarnessIPCServer, send_ipc_command
from tgharness.core.router import dispatch_request
from tgharness.core.serialization import to_jsonable


class FakeApp:
    async def get_me(self):
        return {"id": 1, "first_name": "Agent"}

    async def echo(self, value=None):
        return {"value": value}

    def numbers(self, count=5):
        async def gen():
            for value in range(count):
                yield value
        return gen()

    async def invoke(self, query, **kwargs):
        return {"query": query.__dict__, "invoke": kwargs}

    async def send_document(self, chat_id, document, **kwargs):
        return {"chat_id": chat_id, "document": document, **kwargs}


class AuthTests(unittest.IsolatedAsyncioTestCase):
    def test_write_config_permissions_and_load(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.yaml"
            workdir = root / "data"
            saved = write_config(
                api_id=12345,
                api_hash="secret-hash",
                session_name="agent",
                workdir=workdir,
                config_path=config_path,
            )
            self.assertEqual(saved, config_path)
            self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
            loaded = Config(saved)
            self.assertEqual(loaded.api_id, 12345)
            self.assertEqual(loaded.api_hash, "secret-hash")
            self.assertEqual(loaded.session_name, "agent")
            self.assertEqual(loaded.workdir, workdir.resolve())
            self.assertEqual(loaded.default_account, "default")
            self.assertEqual(loaded.account("default").session_name, "agent")

    async def test_login_2fa_hint_flow(self):
        class FakeLoginApp:
            def __init__(self):
                self.disconnected = False

            async def connect(self):
                return False

            async def send_code(self, phone):
                self.phone = phone
                return pytypes.SimpleNamespace(
                    type=pytypes.SimpleNamespace(name="APP"),
                    timeout=60,
                    phone_code_hash="hash",
                )

            async def sign_in(self, phone, phone_code_hash, code):
                self.sign_in_args = (phone, phone_code_hash, code)
                raise SessionPasswordNeeded()

            async def get_password_hint(self):
                return "blue cat"

            async def check_password(self, password):
                self.password = password
                return pytypes.SimpleNamespace(id=7, first_name="Agent", last_name="", username="agent")

            async def disconnect(self):
                self.disconnected = True

        with tempfile.TemporaryDirectory() as directory:
            cfg_path = Path(directory) / "config.yaml"
            cfg = Config(cfg_path)
            cfg.api_id = 1
            cfg.api_hash = "hash"
            cfg.workdir = Path(directory)
            cfg.session_name = "agent"
            cfg.session_path = str(Path(directory) / "agent")
            app = FakeLoginApp()
            fake_stdin = pytypes.SimpleNamespace(isatty=lambda: True)
            output = StringIO()
            with patch.object(auth, "get_client", return_value=app), \
                 patch.object(auth.sys, "stdin", fake_stdin), \
                 patch.object(auth, "_prompt", return_value="+41123456789"), \
                 patch.object(auth.getpass, "getpass", side_effect=["12345", "correct horse"]), \
                 redirect_stdout(output):
                user = await auth.login_interactive(cfg=cfg)

            self.assertEqual(user.id, 7)
            self.assertEqual(app.sign_in_args, ("+41123456789", "hash", "12345"))
            self.assertEqual(app.password, "correct horse")
            self.assertTrue(app.disconnected)
            self.assertIn("Two-Step Verification required", output.getvalue())
            self.assertIn("Hint: blue cat", output.getvalue())


class SkillPackageTests(unittest.TestCase):
    def test_skill_metadata_and_references(self):
        import yaml

        root = Path(__file__).resolve().parents[1]
        skill_dir = root / "skills" / "telegram-harness"
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = yaml.safe_load(text.split("---\n", 2)[1])
        self.assertEqual(frontmatter["name"], "telegram-harness")
        self.assertEqual(str(frontmatter["version"]), "0.5.2")
        self.assertLessEqual(len(frontmatter["description"]), 60)
        self.assertTrue(frontmatter["description"].endswith("."))
        self.assertEqual(frontmatter["metadata"]["hermes"]["category"], "communication")
        self.assertIn("terminal", frontmatter["metadata"]["hermes"]["requires_toolsets"])
        self.assertIn("https://telegramplayground.github.io/pyrogram/index.html", text)
        for heading in (
            "## When to Use",
            "## Prerequisites",
            "## How to Run",
            "## Quick Reference",
            "## Procedure",
            "## Pitfalls",
            "## Verification",
        ):
            self.assertIn(heading, text)
        for reference in ("ACCOUNTS.md", "AUTH.md", "CLI.md", "INSTALLATION.md", "JSON_PROTOCOL.md", "PYROTGFORK.md", "RECIPES.md"):
            self.assertTrue((skill_dir / "references" / reference).exists())
        openai = yaml.safe_load((skill_dir / "agents" / "openai.yaml").read_text(encoding="utf-8"))
        short_description = openai["interface"]["short_description"]
        self.assertGreaterEqual(len(short_description), 25)
        self.assertLessEqual(len(short_description), 64)


    def test_upgrade_docs_and_installer_are_in_sync(self):
        root = Path(__file__).resolve().parents[1]
        install = (root / "install.sh").read_text(encoding="utf-8")
        readme = (root / "README.md").read_text(encoding="utf-8")
        skill = (root / "skills" / "telegram-harness" / "SKILL.md").read_text(encoding="utf-8")
        installation = (root / "skills" / "telegram-harness" / "references" / "INSTALLATION.md").read_text(encoding="utf-8")
        self.assertIn("--upgrade", install)
        self.assertIn("--upgrade", readme)
        self.assertIn("--upgrade", skill)
        self.assertIn("--upgrade", installation)
        self.assertIn("detect_existing_skill_targets", install)
        self.assertTrue((root / "CHANGELOG.md").exists())


class SerializationTests(unittest.TestCase):
    def test_recursive_container(self):
        value = []
        value.append(value)
        self.assertEqual(to_jsonable(value), ["<list:recursive>"])

    def test_tagged_values(self):
        self.assertEqual(decode_value({"$enum": "ParseMode.MARKDOWN"}), ParseMode.MARKDOWN)
        button = decode_value({"$type": "InlineKeyboardButton", "kwargs": {"text": "x"}})
        self.assertEqual(button.text, "x")
        peer = decode_value({"$raw_type": "InputPeerSelf", "kwargs": {}})
        self.assertIsInstance(peer, InputPeerSelf)
        query = decode_value({"$raw_function": "messages.GetHistory", "kwargs": {"limit": 2}})
        self.assertIsInstance(query, GetHistory)
        self.assertEqual(query.limit, 2)


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_generic_client_call(self):
        data, meta = await call_client_method(FakeApp(), "echo", {"value": 3})
        self.assertEqual(data, {"value": 3})
        self.assertEqual(meta, {})

    async def test_generator_cap(self):
        data, meta = await call_client_method(FakeApp(), "numbers", {"count": 5}, 3)
        self.assertEqual(data, [0, 1, 2])
        self.assertTrue(meta["truncated"])
        self.assertEqual(meta["collected"], 3)

    async def test_raw_gateway(self):
        data = await invoke_raw(FakeApp(), "messages.GetHistory", {"limit": 2}, retries=1)
        self.assertEqual(data["query"], {"limit": 2})
        self.assertEqual(data["invoke"]["retries"], 1)

    async def test_python_await_expression_returns_value(self):
        data = await execute_python(FakeApp(), "await app.get_me()")
        self.assertEqual(data["id"], 1)

    async def test_python_comparison_expression_returns_value(self):
        data = await execute_python(FakeApp(), "1 == 1")
        self.assertTrue(data)

    async def test_upload_convenience(self):
        result = await dispatch(
            FakeApp(),
            "upload",
            {"chat_id": "@chat", "file": "./report.pdf", "caption": "Report"},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["document"], "./report.pdf")

    async def test_dispatch_envelope(self):
        result = await dispatch(FakeApp(), "call", {"method": "echo", "params": {"value": "ok"}}, request_id="r1")
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["value"], "ok")
        self.assertEqual(result["meta"]["request_id"], "r1")
        self.assertEqual(result["meta"]["operation"], "call")


class CLITests(unittest.TestCase):
    def test_call_parser(self):
        parser = build_parser()
        ns = parser.parse_args(["call", "get_users", "--params", '{"user_ids":["me"]}', "--collect-limit", "2"])
        command, args = _command_args(ns)
        self.assertEqual(command, "call")
        self.assertEqual(args["method"], "get_users")
        self.assertEqual(args["params"]["user_ids"], ["me"])
        self.assertEqual(args["collect_limit"], 2)

    def test_exec_alias(self):
        parser = build_parser()
        ns = parser.parse_args(["exec", "await app.get_me()"])
        command, args = _command_args(ns)
        self.assertEqual(command, "python")
        self.assertEqual(args["code"], "await app.get_me()")

    def test_upload_parser(self):
        parser = build_parser()
        ns = parser.parse_args(["upload", "@chat", "./report.pdf", "--caption", "Report", "--silent"])
        command, args = _command_args(ns)
        self.assertEqual(command, "upload")
        self.assertEqual(args["chat_id"], "@chat")
        self.assertEqual(args["file"], "./report.pdf")
        self.assertTrue(args["disable_notification"])

    def test_setup_and_login_parser(self):
        parser = build_parser()
        setup = parser.parse_args(["setup", "--no-login", "--session", "agent"])
        self.assertEqual(setup.command, "setup")
        self.assertTrue(setup.no_login)
        self.assertEqual(setup.session_name, "agent")
        login = parser.parse_args(["login", "--phone", "+41123456789"])
        self.assertEqual(login.command, "login")
        self.assertEqual(login.phone, "+41123456789")

    def test_multi_account_selection_parser(self):
        parser = build_parser()
        ns = parser.parse_args(["--accounts", "main,alt", "send", "me", "hi"])
        self.assertEqual(ns.accounts, ["main", "alt"])
        ns = parser.parse_args(["--all-accounts", "me"])
        self.assertTrue(ns.all_accounts)

    def test_account_management_parser(self):
        parser = build_parser()
        ns = parser.parse_args(["account", "info", "alt", "--photos", "3", "--download-photos"])
        self.assertEqual(ns.account_command, "info")
        self.assertEqual(ns.name, "alt")
        self.assertEqual(ns.photos, 3)
        self.assertTrue(ns.download_photos)


class MultiAccountConfigTests(unittest.TestCase):
    def test_legacy_config_materializes_and_preserves_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "config.yaml"
            path.write_text(
                "telegram:\n"
                "  api_id: 1\n"
                "  api_hash: hash\n"
                "  session_name: legacy\n"
                f"  workdir: {root / 'data'}\n",
                encoding="utf-8",
            )
            cfg = Config(path)
            self.assertEqual(cfg.default_account, "default")
            self.assertEqual(cfg.account("default").session_name, "legacy")
            cfg.add_account("alt")
            self.assertEqual(cfg.account_names(), ["default", "alt"])
            self.assertEqual(cfg.default_account, "default")
            reloaded = Config(path)
            self.assertEqual(reloaded.account("default").session_name, "legacy")
            self.assertEqual(reloaded.account("alt").session_name, "alt")

    def test_enable_disable_default_and_remove(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "config.yaml"
            write_config(api_id=1, api_hash="hash", workdir=root / "data", config_path=path)
            cfg = Config(path)
            cfg.add_account("alt", enabled=False)
            self.assertFalse(cfg.account("alt", allow_disabled=True).enabled)
            with self.assertRaises(RuntimeError):
                cfg.account("alt")
            cfg.set_account_enabled("alt", True)
            cfg.set_default_account("alt")
            self.assertEqual(cfg.default_account, "alt")
            removed = cfg.remove_account("default")
            self.assertEqual(removed.name, "default")
            self.assertEqual(cfg.account_names(), ["alt"])

    def test_duplicate_session_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "config.yaml"
            write_config(api_id=1, api_hash="hash", session_name="shared", workdir=root / "data", config_path=path)
            cfg = Config(path)
            with self.assertRaisesRegex(ValueError, "distinct session"):
                cfg.add_account("alt", session_name="shared")

    def test_duplicate_sessions_in_manual_config_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "config.yaml"
            path.write_text(
                "telegram:\n"
                "  api_id: 1\n"
                "  api_hash: hash\n"
                f"  workdir: {root / 'data'}\n"
                "  accounts:\n"
                "    a: {session_name: shared, enabled: true}\n"
                "    b: {session_name: shared, enabled: true}\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "same session file"):
                Config(path)


class AccountIdentityTests(unittest.IsolatedAsyncioTestCase):
    async def test_identity_photo_count_and_download_paths(self):
        class ProfileApp:
            async def get_me(self):
                return pytypes.SimpleNamespace(
                    id=42, first_name="Alice", last_name="Agent", username="alice", phone_number="41123"
                )

            async def get_chat_photos_count(self, chat_id):
                self.count_chat_id = chat_id
                return 2

            async def get_chat(self, chat_id):
                return pytypes.SimpleNamespace(id=42, first_name="Alice", bio="hello")

            def get_chat_photos(self, chat_id, limit=None):
                async def gen():
                    for i in range(min(limit or 2, 2)):
                        yield pytypes.SimpleNamespace(file_id=f"photo-{i}", date=None)
                return gen()

            async def download_media(self, photo, file_name=None, in_memory=False):
                return str(Path(file_name) / f"{photo.file_id}.jpg")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "config.yaml"
            write_config(api_id=1, api_hash="hash", workdir=root / "data", config_path=path)
            cfg = Config(path)
            account_cfg = cfg.account()
            data = await account_identity(
                ProfileApp(),
                account_cfg,
                include_photos=True,
                photo_limit=2,
                download_photos=True,
                download_root=root / "photos",
            )
            self.assertEqual(data["identity"]["id"], 42)
            self.assertEqual(data["profile_photo_count"], 2)
            self.assertEqual(len(data["profile_photos"]), 2)
            self.assertTrue(data["profile_photos"][0]["path"].endswith("photo-0.jpg"))


class RouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_routes_one_and_multiple_accounts(self):
        class FakeConfig:
            default_account = "main"

            def account_names(self, enabled_only=False):
                return ["main", "alt"]

            def account(self, name=None, allow_disabled=False):
                selected = name or "main"
                if selected not in {"main", "alt"}:
                    raise KeyError(selected)
                return pytypes.SimpleNamespace(name=selected, enabled=True)

        class RoutedApp(FakeApp):
            def __init__(self, name):
                self.name = name

            async def get_me(self):
                return {"account": self.name}

        class FakePool:
            def __init__(self):
                self.config = FakeConfig()

            async def get(self, name):
                return RoutedApp(name)

        single = await dispatch_request(FakePool(), "me", request_id="r")
        self.assertTrue(single["ok"])
        self.assertEqual(single["data"]["account"], "main")
        self.assertEqual(single["meta"]["account"], "main")

        batch = await dispatch_request(FakePool(), "me", request_id="r", account_names=["main", "alt"])
        self.assertTrue(batch["ok"])
        self.assertEqual([x["account"] for x in batch["data"]["results"]], ["main", "alt"])
        self.assertEqual(batch["meta"]["success_count"], 2)


class AccountInspectionRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_account_info_can_target_multiple_accounts(self):
        class AccountCfg:
            def __init__(self, name, root):
                self.name = name
                self.enabled = True
                self.workdir = root

            def public_dict(self, default=False):
                return {
                    "name": self.name,
                    "session_name": self.name,
                    "enabled": True,
                    "default": default,
                    "session_file": str(self.workdir / f"{self.name}.session"),
                    "session_exists": False,
                    "in_memory": False,
                    "no_updates": False,
                }

        class ConfigForInfo:
            default_account = "main"

            def __init__(self, root):
                self.root = root
                self.download_dir = root / "downloads"

            def account_names(self, enabled_only=False):
                return ["main", "alt"]

            def account(self, name=None, allow_disabled=False):
                selected = name or self.default_account
                if selected not in {"main", "alt"}:
                    raise KeyError(selected)
                return AccountCfg(selected, self.root)

        class InfoApp:
            def __init__(self, name):
                self.name = name

            async def get_me(self):
                return {"id": 1 if self.name == "main" else 2, "username": self.name}

            async def get_chat_photos_count(self, chat_id):
                return 3

            async def get_chat(self, chat_id):
                return {"id": 1 if self.name == "main" else 2, "username": self.name}

        class PoolForInfo:
            def __init__(self, root):
                self.config = ConfigForInfo(root)

            async def get(self, name):
                return InfoApp(name)

        with tempfile.TemporaryDirectory() as directory:
            result = await dispatch_request(
                PoolForInfo(Path(directory)),
                "account_info",
                request_id="info",
                account_names=["main", "alt"],
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["meta"]["success_count"], 2)
        self.assertEqual(
            [child["data"]["identity"]["username"] for child in result["data"]["results"]],
            ["main", "alt"],
        )


class IPCTests(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip(self):
        async def handler(app, command, args, request_id=None):
            return {
                "ok": True,
                "data": {"command": command, "args": args},
                "error": None,
                "meta": {"request_id": request_id},
            }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "h.sock"
            server = HarnessIPCServer(FakeApp(), handler, path)
            await server.start()
            old_socket = __import__("tgharness.core.ipc", fromlist=["config"]).config.ipc_socket
            __import__("tgharness.core.ipc", fromlist=["config"]).config.ipc_socket = path
            try:
                response = await send_ipc_command("me", {"x": 1}, request_id="abc")
                self.assertTrue(response["ok"])
                self.assertEqual(response["data"]["command"], "me")
                self.assertEqual(response["meta"]["request_id"], "abc")
                self.assertEqual(response["meta"]["transport"], "ipc")
            finally:
                __import__("tgharness.core.ipc", fromlist=["config"]).config.ipc_socket = old_socket
                await server.stop()

    async def test_account_selection_round_trip(self):
        async def handler(app, command, args, request_id=None, account_names=None, all_accounts=False):
            return {
                "ok": True,
                "data": {"account_names": account_names, "all_accounts": all_accounts},
                "error": None,
                "meta": {"request_id": request_id},
            }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "h.sock"
            server = HarnessIPCServer(FakeApp(), handler, path)
            await server.start()
            old_socket = __import__("tgharness.core.ipc", fromlist=["config"]).config.ipc_socket
            __import__("tgharness.core.ipc", fromlist=["config"]).config.ipc_socket = path
            try:
                response = await send_ipc_command("me", account_names=["main", "alt"], request_id="abc")
                self.assertEqual(response["data"]["account_names"], ["main", "alt"])
                self.assertFalse(response["data"]["all_accounts"])
            finally:
                __import__("tgharness.core.ipc", fromlist=["config"]).config.ipc_socket = old_socket
                await server.stop()

    async def test_second_server_does_not_replace_live_socket(self):
        async def handler(app, command, args, request_id=None):
            return {"ok": True, "data": None, "error": None, "meta": {}}

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "h.sock"
            first = HarnessIPCServer(FakeApp(), handler, path)
            second = HarnessIPCServer(FakeApp(), handler, path)
            await first.start()
            try:
                with self.assertRaises(RuntimeError):
                    await second.start()
                await second.stop()
                self.assertTrue(path.exists())
            finally:
                await first.stop()


if __name__ == "__main__":
    unittest.main()
