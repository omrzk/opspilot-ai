from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("s3cure-Password!")
    assert hashed != "s3cure-Password!"
    assert verify_password("s3cure-Password!", hashed)
    assert not verify_password("wrong", hashed)


def test_verify_password_bad_hash_returns_false():
    assert not verify_password("anything", "not-a-bcrypt-hash")


def test_token_roundtrip():
    token = create_access_token("user-123")
    assert decode_access_token(token) == "user-123"


def test_tampered_token_rejected():
    token = create_access_token("user-123")
    assert decode_access_token(token + "x") is None
    assert decode_access_token("garbage") is None
