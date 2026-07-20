from app.core.security import hash_password as get_password_hash, verify_password


def test_password_hashing_handles_long_passwords():
    long_password = "a" * 90

    hashed_password = get_password_hash(long_password)

    assert hashed_password
    assert verify_password(long_password, hashed_password) is True
