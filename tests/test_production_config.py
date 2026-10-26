"""Fail-closed production configuration regression tests."""
import base64

import pytest

from app import config


def _valid_production_config(monkeypatch):
    monkeypatch.setattr(config, "ENVIRONMENT", "production")
    monkeypatch.setattr(config, "ADMIN_API_KEY", "a" * 40)
    monkeypatch.setattr(config, "SIGNING_SECRET", "s" * 40)
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://user:password@db.example:5432/cyraduct")
    monkeypatch.setattr(config, "TEST_ADMIN_KEY", "")
    monkeypatch.setenv("CYRADUCT_PRIVATE_KEY_B64", base64.b64encode(b"k" * 32).decode("ascii"))
    monkeypatch.setenv("CYRADUCT_KEY_ID", "cyraduct-prod-2026-01")


def test_production_configuration_accepts_valid_values(monkeypatch):
    _valid_production_config(monkeypatch)
    config.validate_startup()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("ADMIN_API_KEY", "dev-insecure-admin-key", "CYRADUCT_ADMIN_KEY"),
        ("ADMIN_API_KEY", "short", "CYRADUCT_ADMIN_KEY"),
        ("SIGNING_SECRET", "dev-insecure-secret-change-me", "CYRADUCT_SIGNING_SECRET"),
        ("SIGNING_SECRET", "short", "CYRADUCT_SIGNING_SECRET"),
        ("DATABASE_URL", "sqlite:///./cyraduct.db", "CYRADUCT_DATABASE_URL"),
    ],
)
def test_production_rejects_unsafe_values(monkeypatch, field, value, message):
    _valid_production_config(monkeypatch)
    monkeypatch.setattr(config, field, value)
    with pytest.raises(RuntimeError, match=message):
        config.validate_startup()


@pytest.mark.parametrize("encoded", ["", "not-base64!!", base64.b64encode(b"short").decode("ascii")])
def test_production_rejects_missing_or_invalid_signing_key(monkeypatch, encoded):
    _valid_production_config(monkeypatch)
    monkeypatch.setenv("CYRADUCT_PRIVATE_KEY_B64", encoded)
    with pytest.raises(RuntimeError, match="CYRADUCT_PRIVATE_KEY_B64"):
        config.validate_startup()


def test_production_requires_explicit_non_development_key_id(monkeypatch):
    _valid_production_config(monkeypatch)
    monkeypatch.setenv("CYRADUCT_KEY_ID", "cyraduct-dev-key-1")
    with pytest.raises(RuntimeError, match="CYRADUCT_KEY_ID"):
        config.validate_startup()


def test_production_test_key_must_be_long_and_distinct(monkeypatch):
    _valid_production_config(monkeypatch)
    monkeypatch.setattr(config, "TEST_ADMIN_KEY", "a" * 40)
    with pytest.raises(RuntimeError, match="must differ"):
        config.validate_startup()

    monkeypatch.setattr(config, "TEST_ADMIN_KEY", "short")
    with pytest.raises(RuntimeError, match="at least 32"):
        config.validate_startup()


def test_non_production_does_not_require_production_secrets(monkeypatch):
    monkeypatch.setattr(config, "ENVIRONMENT", "test")
    monkeypatch.setattr(config, "ADMIN_API_KEY", "dev-insecure-admin-key")
    monkeypatch.setattr(config, "SIGNING_SECRET", "dev-insecure-secret-change-me")
    monkeypatch.setattr(config, "DATABASE_URL", "sqlite:///./cyraduct.db")
    monkeypatch.delenv("CYRADUCT_PRIVATE_KEY_B64", raising=False)
    monkeypatch.delenv("CYRADUCT_KEY_ID", raising=False)
    config.validate_startup()
