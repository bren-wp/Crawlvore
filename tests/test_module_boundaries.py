"""Regression checks for the compatibility facades and workspace-scoped routes."""
import unittest
from types import SimpleNamespace
from email.message import Message

import core
import company_fields
import company_store
import registry
import registry_access
import registry_client
from local_http_response import LocalResponseHandler
from local_http_routes import make_handler


class ModuleBoundaryTests(unittest.TestCase):
    def test_existing_imports_keep_the_same_implementations(self):
        for name in ("COLS", "FIELDS", "ENTITY_KINDS", "norm", "formula_safe"):
            self.assertIs(getattr(core, name), getattr(company_fields, name))
        self.assertIs(core.Store, company_store.Store)
        for name in ("credentials", "configured", "RegistryAccess"):
            self.assertIs(getattr(registry, name), getattr(registry_access, name))
        for name in ("BASE", "TOKEN_URL", "SPEC_URL", "Client", "TransientRegistryError"):
            self.assertIs(getattr(registry, name), getattr(registry_client, name))

    def test_http_handler_uses_only_its_workspace_token(self):
        def handler(token):
            dependencies = dict.fromkeys((
                "ROOT", "active", "collector", "database", "gb_download",
                "import_lock", "integrity", "national", "protected", "queue",
                "recovery", "registry", "registry_access", "search_integrity",
                "selection", "store", "transfers", "ui_ready", "ui_ready_lock"))
            cls = make_handler(TOKEN=token, args=SimpleNamespace(worker=True),
                               **dependencies)
            self.assertTrue(issubclass(cls, LocalResponseHandler))
            instance = object.__new__(cls)
            instance.server = SimpleNamespace(server_port=49152)
            instance.headers = Message()
            instance.headers["Host"] = "127.0.0.1:49152"
            instance.headers["Cookie"] = "crawlvora_session_49152=" + token
            return instance

        a = handler("a" * 64)
        b = handler("b" * 64)
        self.assertTrue(a.authorized())
        self.assertTrue(a.session_authorized())
        self.assertTrue(b.session_authorized())
        b.headers.replace_header("Cookie", a.headers["Cookie"])
        self.assertFalse(b.session_authorized())
        a.headers.replace_header("Host", "example.invalid:49152")
        self.assertFalse(a.authorized())
