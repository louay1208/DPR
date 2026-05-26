"""Automated Role-Based Access Control (RBAC) security verification tests.

Verifies page/API security limits, permissions separation, and user management rules.
Usage:
    uv run python tests/test_auth_rbac.py
"""

import sys
from pathlib import Path
import sqlite3

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from main import app
from app.services.database import get_connection, init_database

def setup_test_users():
    """Ensure we have a clean set of test users in the database."""
    conn = get_connection()
    try:
        # Check if default admin exists, if not, create one
        cursor = conn.execute("SELECT id FROM users WHERE email = 'admin@etap.com'")
        admin = cursor.fetchone()
        
        # We can leverage the existing auth router helpers or seed directly
        from app.routers.auth import hash_password
        
        if not admin:
            salt = "adminsalt123456"
            pwd_hash = hash_password("admin", salt)
            conn.execute(
                """INSERT INTO users (full_name, email, company, role, password_hash, salt)
                   VALUES ('Default Admin', 'admin@etap.com', 'ETAP', 'admin', ?, ?)""",
                (pwd_hash, salt)
            )
            
        # Clean up any previous test operator
        conn.execute("DELETE FROM users WHERE email = 'test_operator@etap.com'")
        conn.execute("DELETE FROM users WHERE email = 'test_temp@etap.com'")
        
        # Create a test operator
        salt_op = "operatorsalt123"
        pwd_hash_op = hash_password("operator123", salt_op)
        conn.execute(
            """INSERT INTO users (full_name, email, company, role, password_hash, salt)
               VALUES ('Test Operator', 'test_operator@etap.com', 'ETAP', 'user', ?, ?)""",
            (pwd_hash_op, salt_op)
        )
        
        conn.commit()
    finally:
        conn.close()

def run_tests():
    print("=" * 60)
    print("  DPR Security RBAC Integration Verification")
    print("=" * 60)
    
    # Initialize the database
    init_database()
    setup_test_users()
    
    client = TestClient(app)
    
    # ── Test 1: Session & Authentication Endpoint Checks ──
    print("\n[Test 1] Authenticating sessions...")
    
    # Login Admin
    res_admin = client.post("/api/auth/login", json={
        "email": "admin@etap.com",
        "password": "admin"
    })
    assert res_admin.status_code == 200, "Admin login failed"
    admin_data = res_admin.json()
    admin_token = admin_data["token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("  [PASS] Admin logged in successfully")
    
    # Login Operator
    res_op = client.post("/api/auth/login", json={
        "email": "test_operator@etap.com",
        "password": "operator123"
    })
    assert res_op.status_code == 200, "Operator login failed"
    op_data = res_op.json()
    op_token = op_data["token"]
    op_headers = {"Authorization": f"Bearer {op_token}"}
    op_id = op_data["user"]["id"]
    print("  [PASS] Operator logged in successfully")
    
    # ── Test 2: Unauthenticated Access Constraints ──
    print("\n[Test 2] Verifying unauthenticated constraints...")
    
    # Missing Token
    res = client.get("/api/users")
    assert res.status_code == 401, "Expected 401 on missing token"
    assert res.json()["detail"] == "Missing or invalid token"
    
    # Invalid Token
    res = client.get("/api/users", headers={"Authorization": "Bearer invalidtoken123"})
    assert res.status_code == 401, "Expected 401 on invalid token"
    print("  [PASS] Invalid or missing tokens successfully rejected (401)")
    
    # ── Test 3: Standard Operator Privilege Separation ──
    print("\n[Test 3] Verifying standard operator role-based restrictions...")
    
    # Blocked from viewing user directory
    res = client.get("/api/users", headers=op_headers)
    assert res.status_code == 403, "Operator was able to view user directory!"
    assert "Administrator privileges required" in res.json()["detail"]
    
    # Blocked from creating new accounts
    res = client.post("/api/users", headers=op_headers, json={
        "full_name": "Hack Attack",
        "email": "hacker@etap.com",
        "company": "External",
        "role": "admin",
        "password": "password"
    })
    assert res.status_code == 403, "Operator was able to post to user registration!"
    
    # Blocked from updating roles
    res = client.put(f"/api/users/{op_id}/role", headers=op_headers, json={"role": "admin"})
    assert res.status_code == 403, "Operator was able to self-promote!"
    
    # Blocked from password resetting other accounts
    res = client.put("/api/users/1/reset-password", headers=op_headers, json={"password": "newpassword"})
    assert res.status_code == 403, "Operator was able to trigger password reset!"
    
    # Blocked from deleting accounts
    res = client.delete("/api/users/1", headers=op_headers)
    assert res.status_code == 403, "Operator was able to delete accounts!"
    print("  [PASS] Operator securely blocked from all user administration routes (403)")
    
    # ── Test 4: Shared Feature Verification ──
    print("\n[Test 4] Verifying operator access to shared workflow features...")
    
    # Concessions configuration (Accessible to both user and admin)
    res = client.get("/api/concessions", headers=op_headers)
    assert res.status_code == 200, "Operator blocked from concessions access!"
    
    # Unit conversions (Accessible to both user and admin)
    res = client.get("/api/uom", headers=op_headers)
    assert res.status_code == 200, "Operator blocked from unit conversions access!"
    print("  [PASS] Operator successfully verified to access shared parameters (Concessions & UOM)")
    
    # ── Test 5: Full Administrator User Management CRUD Flow ──
    print("\n[Test 5] Verifying administrator user management CRUD operations...")
    
    # 1. Create a temporary operator account
    res = client.post("/api/users", headers=admin_headers, json={
        "full_name": "Temporary Operator",
        "email": "test_temp@etap.com",
        "company": "SODEPS",
        "role": "user",
        "password": "tempPassword123"
    })
    assert res.status_code == 201, "Admin failed to create new operator account"
    print("  [PASS] Admin successfully created a new operator account")
    
    # Fetch user directory to verify inclusion and ID
    res = client.get("/api/users", headers=admin_headers)
    assert res.status_code == 200
    users = res.json()
    temp_user = next((u for u in users if u["email"] == "test_temp@etap.com"), None)
    assert temp_user is not None, "Created user not found in directory"
    temp_id = temp_user["id"]
    print(f"  [PASS] Created user successfully listed in user directory (ID={temp_id})")
    
    # 2. Update role from Operator to Admin
    res = client.put(f"/api/users/{temp_id}/role", headers=admin_headers, json={"role": "admin"})
    assert res.status_code == 200, "Admin failed to update user role"
    
    # Verify role change
    res = client.get("/api/users", headers=admin_headers)
    temp_user_updated = next((u for u in res.json() if u["id"] == temp_id), None)
    assert temp_user_updated["role"] == "admin", "Role update verification failed"
    print("  [PASS] User role successfully elevated to 'admin'")
    
    # 3. Reset password and verify login
    res = client.put(f"/api/users/{temp_id}/reset-password", headers=admin_headers, json={"password": "newTempPassword99"})
    assert res.status_code == 200, "Admin failed to reset user password"
    
    # Verify login with new password
    res_login_new = client.post("/api/auth/login", json={
        "email": "test_temp@etap.com",
        "password": "newTempPassword99"
    })
    assert res_login_new.status_code == 200, "Failed to login with reset password"
    print("  [PASS] User successfully logged in with newly reset password")
    
    # Verify old password fails
    res_login_old = client.post("/api/auth/login", json={
        "email": "test_temp@etap.com",
        "password": "tempPassword123"
    })
    assert res_login_old.status_code == 401, "Old password was not invalidated!"
    print("  [PASS] Old password successfully invalidated")
    
    # ── Test 6: Security Boundary Assertions ──
    print("\n[Test 6] Verifying safety boundaries...")
    
    # Prevent Self-Deletion
    admin_id = admin_data["user"]["id"]
    res = client.delete(f"/api/users/{admin_id}", headers=admin_headers)
    assert res.status_code == 400, "Self-deletion should be blocked!"
    assert "You cannot delete your own account" in res.json()["detail"]
    print("  [PASS] Admin self-deletion prevented successfully")
    
    # Prevent demoting last admin
    # Demote the temp admin back to user so admin@etap.com is the only admin
    res = client.put(f"/api/users/{temp_id}/role", headers=admin_headers, json={"role": "user"})
    assert res.status_code == 200
    
    # Attempt to demote the default admin
    res = client.put(f"/api/users/{admin_id}/role", headers=admin_headers, json={"role": "user"})
    assert res.status_code == 400, "Demoting last admin should be blocked!"
    assert "Cannot demote the last administrator" in res.json()["detail"]
    print("  [PASS] Demoting the last administrator prevented successfully")
    
    # Attempt to delete the default admin when they are the only admin (blocked by self-deletion anyway)
    # 4. Delete the temporary user account
    res = client.delete(f"/api/users/{temp_id}", headers=admin_headers)
    assert res.status_code == 200, "Failed to delete temporary operator account"
    
    # Verify deletion
    res = client.get("/api/users", headers=admin_headers)
    temp_deleted = next((u for u in res.json() if u["id"] == temp_id), None)
    assert temp_deleted is None, "User account was not deleted"
    print("  [PASS] Admin successfully deleted temporary user account")
    
    # Clean up test operator
    res = client.delete(f"/api/users/{op_id}", headers=admin_headers)
    assert res.status_code == 200
    print("  [PASS] Cleanup complete")
    
    print("\n" + "=" * 60)
    print("  ALL SECURITY RBAC INTEGRATION TESTS PASSED")
    print("=" * 60)

if __name__ == "__main__":
    try:
        run_tests()
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILURE: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
