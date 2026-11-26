import json
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from tools import configure_registry_owner as owner


class OwnerTests(unittest.TestCase):
    def test_private_repository_guard(self):
        with patch.object(owner,'gh_call',return_value=b'{"visibility":"PUBLIC"}') as call:
            with self.assertRaises(ValueError):
                owner.publish_secrets(('synthetic-id','synthetic-value'))
            self.assertEqual(call.call_count,1)

    def test_secret_metadata_verification(self):
        names=[{'name':'SUDREG_CLIENT_ID'},{'name':'SUDREG_CLIENT_SECRET'}]
        with patch.object(owner,'gh_call',side_effect=[b'{"visibility":"PRIVATE"}',b'production-api',b'',b'',json.dumps(names).encode()]) as call:
            owner.publish_secrets(('synthetic-id','synthetic-value'))
            self.assertEqual(call.call_count,5)
            self.assertEqual(call.call_args_list[2].args[1],b'synthetic-id')
            self.assertEqual(call.call_args_list[3].args[1],b'synthetic-value')
            self.assertNotIn('synthetic-value',call.call_args_list[3].args[0])

    def test_reuse_revoked_vault_is_rejected(self):
        with patch.object(owner,'NativeVault',return_value=Mock(load=Mock(return_value={'authorized':False}))), patch.object(owner,'check') as check:
            with self.assertRaises(ValueError):
                owner.enroll(Path('test-workspace'),reuse=True)
            check.assert_not_called()

    def test_reuse_authorized_vault_no_prompt_or_overwrite(self):
        record={'authorized':True,'client_id':'synthetic-id','client_secret':'synthetic-value'}
        with patch.object(owner,'NativeVault',return_value=Mock(load=Mock(return_value=record))), patch.object(owner,'check') as check, patch.object(owner,'getpass') as prompt, patch.object(owner.RegistryAccess,'apply') as apply:
            self.assertEqual(owner.enroll(Path('test-workspace'),reuse=True),('synthetic-id','synthetic-value'))
            check.assert_called_once_with(('synthetic-id','synthetic-value'))
            prompt.getpass.assert_not_called()
            apply.assert_not_called()
