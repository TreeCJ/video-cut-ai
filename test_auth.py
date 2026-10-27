#!/usr/bin/env python
"""Test authentication system."""

import sys
from pathlib import Path
import requests

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

BASE_URL = "http://127.0.0.1:8464"


def test_login():
    """Test login with admin credentials."""
    print("Testing login...")
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": "admin", "password": "admin123"},
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✓ Login successful!")
        print(f"  User ID: {data['user_id']}")
        print(f"  Username: {data['username']}")
        print(f"  Role: {data['role']}")
        return True
    else:
        print(f"✗ Login failed with status {response.status_code}")
        print(f"  Response: {response.text}")
        return False


def test_get_me(token):
    """Test getting current user info."""
    print("\nTesting /auth/me...")
    response = requests.get(
        f"{BASE_URL}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    if response.status_code == 200:
        user = response.json()
        print(f"✓ Got user info:")
        print(f"  Username: {user['username']}")
        print(f"  Email: {user['email']}")
        print(f"  Role: {user['role']}")
        return True
    else:
        print(f"✗ Failed with status {response.status_code}")
        return False


def test_unauthorized():
    """Test accessing protected route without auth."""
    print("\nTesting unauthorized access...")
    response = requests.get(f"{BASE_URL}/auth/me")

    if response.status_code == 401:
        print(f"✓ Correctly rejected unauthorized request (401)")
        return True
    else:
        print(f"✗ Should have returned 401, got {response.status_code}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Authentication System Test")
    print("=" * 60)

    # Test login
    if not test_login():
        sys.exit(1)

    # Get token from login response
    login_response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_response.json()["access_token"]

    # Test get current user
    if not test_get_me(token):
        sys.exit(1)

    # Test unauthorized access
    if not test_unauthorized():
        sys.exit(1)

    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)
