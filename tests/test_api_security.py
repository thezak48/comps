import unittest

from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError

from api.models import ComparisonCreate, ExpirationDays
from auth import comparison_never_expires, require_comparison_write_access


class ExpirationValidationTests(unittest.TestCase):
    def test_accepts_supported_expiration_settings(self):
        comparison = ComparisonCreate(
            expiration_type="from_creation",
            expiration_days=30,
        )

        self.assertEqual(comparison.expiration_type, "from_creation")
        self.assertEqual(comparison.expiration_days, 30)

    def test_rejects_unsupported_expiration_days(self):
        with self.assertRaises(ValidationError):
            ComparisonCreate(expiration_days=365)

    def test_rejects_unsupported_expiration_type(self):
        with self.assertRaises(ValidationError):
            ComparisonCreate(expiration_type="never")

    def test_accepts_supported_expiration_day_from_form_string(self):
        expiration_days = TypeAdapter(ExpirationDays).validate_python("7")

        self.assertEqual(expiration_days, 7)


class ComparisonWriteAccessTests(unittest.TestCase):
    def test_owner_can_edit_owned_comparison(self):
        require_comparison_write_access({"user_id": 42}, {"id": 42})

    def test_anonymous_user_cannot_edit_owned_comparison(self):
        with self.assertRaises(HTTPException) as raised:
            require_comparison_write_access({"user_id": 42}, None)

        self.assertEqual(raised.exception.status_code, 403)

    def test_different_user_cannot_edit_owned_comparison(self):
        with self.assertRaises(HTTPException) as raised:
            require_comparison_write_access({"user_id": 42}, {"id": 7})

        self.assertEqual(raised.exception.status_code, 403)

    def test_anonymous_comparison_remains_editable(self):
        require_comparison_write_access({"user_id": None}, None)


class NeverExpireEntitlementTests(unittest.TestCase):
    def test_anonymous_user_cannot_create_non_expiring_comparison(self):
        self.assertFalse(comparison_never_expires(None))

    def test_user_without_entitlement_cannot_create_non_expiring_comparison(self):
        user = {"never_expire_comparisons": False}

        self.assertFalse(comparison_never_expires(user))

    def test_entitled_user_can_create_non_expiring_comparison(self):
        user = {"never_expire_comparisons": True}

        self.assertTrue(comparison_never_expires(user))

    def test_entitled_user_can_explicitly_enable_expiration(self):
        user = {"never_expire_comparisons": True}

        self.assertFalse(comparison_never_expires(user, expiration_enabled=True))


if __name__ == "__main__":
    unittest.main()
