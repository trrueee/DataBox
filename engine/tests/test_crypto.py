"""Tests for crypto module — encrypt/decrypt password flow."""
import pytest
from engine.crypto import encrypt_password, decrypt_password, get_or_create_key


def test_encrypt_returns_tuple() -> None:
    cipher, nonce = encrypt_password("mypassword")
    assert isinstance(cipher, str)
    assert isinstance(nonce, str)
    assert len(cipher) > 0
    assert len(nonce) > 0


def test_decrypt_restores_original() -> None:
    original = "MySecureP@ssw0rd!"
    cipher, nonce = encrypt_password(original)
    decrypted = decrypt_password(cipher, nonce)
    assert decrypted == original


def test_encrypt_empty_password() -> None:
    cipher, nonce = encrypt_password("")
    assert cipher == ""
    assert nonce == ""


def test_decrypt_empty_credentials() -> None:
    assert decrypt_password("", "") == ""


def test_encrypt_different_passwords_have_different_ciphertexts() -> None:
    c1, n1 = encrypt_password("password1")
    c2, n2 = encrypt_password("password2")
    assert c1 != c2


def test_encrypt_same_password_has_different_ciphertext() -> None:
    """Each encryption should produce unique nonce+ciphertext pair."""
    c1, n1 = encrypt_password("same_password")
    c2, n2 = encrypt_password("same_password")
    assert (c1, n1) != (c2, n2), "AES-GCM should produce unique nonces per encryption"


def test_decrypt_with_wrong_ciphertext_raises() -> None:
    with pytest.raises(ValueError, match="Failed to decrypt"):
        decrypt_password("invalid_base64!!", "invalid_nonce!!")


def test_decrypt_with_wrong_nonce_raises() -> None:
    _, n1 = encrypt_password("password1")
    c2, _ = encrypt_password("password2")
    with pytest.raises(ValueError, match="Failed to decrypt"):
        decrypt_password(c2, n1)


def test_unicode_password() -> None:
    original = "密码测试!@#$%^&*()_+-=[]{}|;':,.<>?/~`"
    cipher, nonce = encrypt_password(original)
    assert decrypt_password(cipher, nonce) == original


def test_long_password() -> None:
    original = "A" * 1000
    cipher, nonce = encrypt_password(original)
    assert decrypt_password(cipher, nonce) == original


def test_key_persistence() -> None:
    """Verify get_or_create_key returns the same key on subsequent calls."""
    key1 = get_or_create_key()
    key2 = get_or_create_key()
    assert key1 == key2
    assert len(key1) == 32  # 256-bit key
