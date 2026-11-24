# Copyright (c) 2024, ALYF GmbH and Contributors
# See license.txt

from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from frappe.tests import IntegrationTestCase, UnitTestCase

from banking.ebics.doctype.ebics_user.ebics_user import initialize
from banking.ebics.manager import EBICSManager


class TestEBICSUser(IntegrationTestCase):
	pass


class TestEBICSUserInitialize(UnitTestCase):
	@patch("banking.ebics.doctype.ebics_user.ebics_user.frappe.local", SimpleNamespace(lang="en"))
	@patch("banking.ebics.doctype.ebics_user.ebics_user.frappe.db")
	@patch("banking.ebics.doctype.ebics_user.ebics_user.get_ebics_manager")
	@patch("banking.ebics.doctype.ebics_user.ebics_user.frappe.get_doc")
	@patch("banking.ebics.doctype.ebics_user.ebics_user.ensure_ebics_is_enabled")
	def test_initialize_commits_after_keys_and_ini(
		self,
		_ensure_ebics_is_enabled,
		get_doc,
		get_ebics_manager,
		mock_db,
	):
		user = MagicMock()
		user.needs_certificates = False
		user.bank = "Test Bank"
		get_doc.return_value = user

		manager = MagicMock()
		manager.create_ini_letter.return_value = b"%PDF-1.4"
		get_ebics_manager.return_value = manager
		mock_db.get_value.return_value = "Test Bank Name"

		tracker = MagicMock()
		tracker.attach_mock(user.save, "save")
		tracker.attach_mock(manager.create_user_keys, "create_user_keys")
		tracker.attach_mock(mock_db.commit, "commit")
		tracker.attach_mock(manager.send_ini, "send_ini")
		tracker.attach_mock(manager.send_hia, "send_hia")

		initialize("EBICS-USER-1", "secret", "sig-secret", 1)

		self.assertEqual(
			tracker.mock_calls,
			[
				call.save(),
				call.create_user_keys(),
				call.commit(),
				call.send_ini(),
				call.commit(),
				call.send_hia(),
			],
		)
		user.attach_ini_letter.assert_called_once_with(b"%PDF-1.4")
		user.db_set.assert_called_once_with("initialized", 1)

	@patch("banking.ebics.doctype.ebics_user.ebics_user.frappe.db")
	@patch("banking.ebics.doctype.ebics_user.ebics_user.get_ebics_manager")
	@patch("banking.ebics.doctype.ebics_user.ebics_user.frappe.get_doc")
	@patch("banking.ebics.doctype.ebics_user.ebics_user.ensure_ebics_is_enabled")
	def test_initialize_commits_keys_and_ini_when_hia_fails(
		self,
		_ensure_ebics_is_enabled,
		get_doc,
		get_ebics_manager,
		mock_db,
	):
		user = MagicMock()
		user.needs_certificates = False
		get_doc.return_value = user

		manager = MagicMock()
		manager.send_hia.side_effect = RuntimeError("HIA failed")
		get_ebics_manager.return_value = manager

		with self.assertRaises(RuntimeError):
			initialize("EBICS-USER-1", "secret", "sig-secret", 1)

		self.assertEqual(mock_db.commit.call_count, 2)
		user.db_set.assert_not_called()

	@patch("banking.ebics.doctype.ebics_user.ebics_user.frappe.db")
	@patch("banking.ebics.doctype.ebics_user.ebics_user.get_ebics_manager")
	@patch("banking.ebics.doctype.ebics_user.ebics_user.frappe.get_doc")
	@patch("banking.ebics.doctype.ebics_user.ebics_user.ensure_ebics_is_enabled")
	def test_initialize_commits_keys_when_ini_fails(
		self,
		_ensure_ebics_is_enabled,
		get_doc,
		get_ebics_manager,
		mock_db,
	):
		user = MagicMock()
		user.needs_certificates = False
		get_doc.return_value = user

		manager = MagicMock()
		manager.send_ini.side_effect = RuntimeError("INI failed")
		get_ebics_manager.return_value = manager

		with self.assertRaises(RuntimeError):
			initialize("EBICS-USER-1", "secret", "sig-secret", 1)

		self.assertEqual(mock_db.commit.call_count, 1)
		manager.send_hia.assert_not_called()

	def test_ebics_manager_send_ini_and_send_hia(self):
		manager = EBICSManager()
		client = MagicMock()
		manager.client = client

		manager.send_ini()
		manager.send_hia()

		client.INI.assert_called_once_with()
		client.HIA.assert_called_once_with()
