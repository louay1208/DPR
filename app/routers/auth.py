from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel
import hashlib
import secrets
import sqlite3
from typing import Optional

from app.services.database import get_connection

router = APIRouter(prefix="/api/auth", tags=["auth"])
users_router = APIRouter(prefix="/api/users", tags=["users"])

class UserRegister(BaseModel):
    full_name: str
    email: str
    company: Optional[str] = ""
    role: str = "user"
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class RoleUpdate(BaseModel):
    role: str

class PasswordReset(BaseModel):
    password: str

def hash_password(password: str, salt: str) -> str:
    """Hash a password using PBKDF2 HMAC SHA256."""
    hash_bytes = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return hash_bytes.hex()

# ── Dependencies ───────────────────────────────────────────────────────

async def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid token"
        )
    token = auth_header.split(" ")[1]
    
    conn = get_connection()
    try:
        cursor = conn.execute(
            """SELECT u.id, u.full_name, u.email, u.company, u.role 
               FROM user_sessions s
               JOIN users u ON s.user_id = u.id
               WHERE s.token = ?""",
            (token,)
        )
        user = cursor.fetchone()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired or invalid"
            )
        return {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "company": user["company"],
            "role": user["role"]
        }
    finally:
        conn.close()

async def require_admin(user = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required"
        )
    return user

# ── Authentication Endpoints ───────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user: UserRegister):
    conn = get_connection()
    try:
        # Check if user already exists
        cursor = conn.execute("SELECT id FROM users WHERE email = ?", (user.email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Email already registered")

        # Create new user
        salt = secrets.token_hex(16)
        pwd_hash = hash_password(user.password, salt)
        
        conn.execute(
            """INSERT INTO users (full_name, email, company, role, password_hash, salt) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user.full_name, user.email, user.company, user.role, pwd_hash, salt)
        )
        conn.commit()
        return {"message": "User created successfully"}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.post("/login")
async def login(credentials: UserLogin):
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT id, full_name, email, company, role, password_hash, salt FROM users WHERE email = ?", 
            (credentials.email,)
        )
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")
            
        pwd_hash = hash_password(credentials.password, user["salt"])
        if pwd_hash != user["password_hash"]:
            raise HTTPException(status_code=401, detail="Invalid email or password")
            
        # Create a new session token
        token = secrets.token_hex(32)
        conn.execute(
            "INSERT INTO user_sessions (token, user_id) VALUES (?, ?)",
            (token, user["id"])
        )
        conn.commit()
        
        return {
            "message": "Login successful",
            "user": {
                "id": user["id"],
                "full_name": user["full_name"],
                "email": user["email"],
                "company": user["company"],
                "role": user["role"]
            },
            "token": token
        }
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.post("/logout")
async def logout(request: Request):
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        conn = get_connection()
        try:
            conn.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
            conn.commit()
        except sqlite3.Error:
            pass
        finally:
            conn.close()
    return {"message": "Logged out successfully"}

# ── User Management Endpoints (Admin Only) ─────────────────────────────

@users_router.get("")
async def get_users(admin = Depends(require_admin)):
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT id, full_name, email, company, role, created_at FROM users ORDER BY created_at DESC"
        )
        users = cursor.fetchall()
        return [
            {
                "id": u["id"],
                "full_name": u["full_name"],
                "email": u["email"],
                "company": u["company"],
                "role": u["role"],
                "created_at": u["created_at"]
            }
            for u in users
        ]
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@users_router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(user: UserRegister, admin = Depends(require_admin)):
    conn = get_connection()
    try:
        # Check if user already exists
        cursor = conn.execute("SELECT id FROM users WHERE email = ?", (user.email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Email already registered")
            
        if user.role not in ["admin", "user"]:
            raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'user'")
            
        # Create new user
        salt = secrets.token_hex(16)
        pwd_hash = hash_password(user.password, salt)
        
        conn.execute(
            """INSERT INTO users (full_name, email, company, role, password_hash, salt) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user.full_name, user.email, user.company, user.role, pwd_hash, salt)
        )
        conn.commit()
        return {"message": "User created successfully"}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@users_router.put("/{id}/role")
async def update_role(id: int, role_data: RoleUpdate, admin = Depends(require_admin)):
    if role_data.role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'user'")
        
    conn = get_connection()
    try:
        # Check if user exists
        cursor = conn.execute("SELECT id, role FROM users WHERE id = ?", (id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Prevent demoting the last admin
        if user["role"] == "admin" and role_data.role != "admin":
            cursor = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
            admin_count = cursor.fetchone()[0]
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot demote the last administrator"
                )

        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role_data.role, id))
        conn.commit()
        return {"message": "Role updated successfully"}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@users_router.put("/{id}/reset-password")
async def reset_password(id: int, pwd_data: PasswordReset, admin = Depends(require_admin)):
    if len(pwd_data.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters long")
        
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT id FROM users WHERE id = ?", (id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")
            
        salt = secrets.token_hex(16)
        pwd_hash = hash_password(pwd_data.password, salt)
        
        conn.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
            (pwd_hash, salt, id)
        )
        # Invalidate active sessions for this user
        conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (id,))
        conn.commit()
        return {"message": "Password reset successfully"}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@users_router.delete("/{id}")
async def delete_user(id: int, admin = Depends(require_admin)):
    if admin["id"] == id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account"
        )
    conn = get_connection()
    try:
        # Check if user exists
        cursor = conn.execute("SELECT id, role FROM users WHERE id = ?", (id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Verify that we don't delete the last admin
        if user["role"] == "admin":
            cursor = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
            admin_count = cursor.fetchone()[0]
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete the last administrator"
                )

        conn.execute("DELETE FROM users WHERE id = ?", (id,))
        conn.commit()
        return {"message": "User deleted successfully"}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
