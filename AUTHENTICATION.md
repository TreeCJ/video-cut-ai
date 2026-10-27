# Authentication & User Management

This document describes the authentication and user management system.

## Features

- **JWT-based Authentication**: Secure token-based authentication with HTTP-only cookies
- **Role-based Access Control**: Three roles (Admin, Editor, Viewer) with different permissions
- **User Management**: Admin panel for creating, editing, and deleting users
- **Password Security**: Bcrypt hashing for secure password storage
- **Session Management**: 24-hour token expiration with automatic renewal

## Quick Start

### 1. Initialize Database

Before first use, initialize the database and create the default admin account:

```bash
python src/video_cut/db/init_db.py
```

This will:
- Create all necessary database tables
- Create a default admin user with credentials:
  - Username: `admin`
  - Password: `admin123`
  - **⚠️ IMPORTANT**: Change this password immediately after first login!

### 2. Start the Server

```bash
video-cut serve
```

Or in development mode:

```bash
uvicorn video_cut.web.app:create_app_dev --reload
```

### 3. Login

Navigate to `http://localhost:8462/login` and login with the admin credentials.

## User Roles

### Admin
- Full access to all features
- Can create, edit, and delete users
- Can manage all videos and projects
- Access to admin panel at `/admin/users`

### Editor
- Can upload and process videos
- Can create and edit clips
- Cannot manage users
- Default role for new users

### Viewer
- Read-only access to videos and clips
- Cannot modify or delete content
- Cannot manage users

## API Endpoints

### Authentication

#### POST `/auth/login`
Login with username and password.

**Request:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "user_id": 1,
  "username": "admin",
  "role": "admin"
}
```

#### POST `/auth/register`
Register a new user (requires admin authentication).

**Request:**
```json
{
  "username": "newuser",
  "email": "user@example.com",
  "password": "securepass",
  "role": "editor"
}
```

#### POST `/auth/logout`
Logout and clear authentication cookie.

#### GET `/auth/me`
Get current user information.

### User Management (Admin Only)

#### GET `/admin/users`
List all users with pagination and filters.

**Query Parameters:**
- `skip`: Number of records to skip (default: 0)
- `limit`: Maximum records to return (default: 100)
- `role`: Filter by role (admin/editor/viewer)
- `is_active`: Filter by active status

#### PUT `/admin/users/{user_id}`
Update user information.

**Request:**
```json
{
  "username": "newname",
  "email": "new@email.com",
  "password": "newpassword",  // optional
  "role": "editor",
  "is_active": true
}
```

#### DELETE `/admin/users/{user_id}`
Soft-delete a user (sets `is_active` to false).

## Security

### Password Hashing
- Uses bcrypt for secure password hashing
- Salts are automatically generated
- Passwords are never stored in plain text

### JWT Tokens
- Tokens expire after 24 hours
- Stored in HTTP-only cookies to prevent XSS attacks
- Signed with HS256 algorithm

### Environment Variables

Configure security settings via environment variables:

```bash
# Change this in production!
JWT_SECRET_KEY=your-super-secret-key-here

# Token expiration (in minutes, default: 1440 = 24 hours)
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

## Database Schema

The system uses the following tables:

- `users`: User accounts
  - `id`: Primary key
  - `username`: Unique username
  - `email`: Unique email address
  - `password_hash`: Bcrypt hashed password
  - `role`: User role (admin/editor/viewer)
  - `is_active`: Account status
  - `created_at`: Creation timestamp
  - `updated_at`: Last update timestamp

## Development

### Adding Authentication to New Routes

To protect a route, use the `get_current_user` dependency:

```python
from fastapi import Depends
from video_cut.auth import get_current_user
from video_cut.db.models import User

@app.get("/protected")
def protected_route(current_user: User = Depends(get_current_user)):
    # Only authenticated users can access
    return {"message": f"Hello {current_user.username}"}
```

To require a specific role:

```python
from video_cut.auth import require_role

@app.get("/admin-only")
def admin_route(current_user: User = Depends(require_role("admin"))):
    # Only admins can access
    return {"message": "Admin access granted"}
```

### Testing

For testing, you can:

1. Use the default admin account (admin/admin123)
2. Create test users via the admin panel
3. Use API endpoints directly with curl or Postman

Example login with curl:

```bash
curl -X POST http://localhost:8462/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  -c cookies.txt
```

## Production Deployment

Before deploying to production:

1. **Change the default admin password** immediately
2. **Set a strong JWT secret**: Generate a random string for `JWT_SECRET_KEY`
3. **Use HTTPS**: Ensure your deployment uses SSL/TLS
4. **Database**: Use MySQL or PostgreSQL instead of SQLite for better performance
5. **Backup**: Regularly backup the user database

Example production environment variables:

```bash
JWT_SECRET_KEY=$(openssl rand -hex 32)  # Generate random 256-bit key
DATABASE_URL=mysql://user:pass@localhost/videocut
```

## Troubleshooting

### "Invalid token" errors
- Check that `JWT_SECRET_KEY` is consistent across server restarts
- Clear browser cookies and login again

### "User not found" after initialization
- Run `init_db.py` again to ensure the admin user exists
- Check database connection settings

### Can't access admin panel
- Verify your user role is "admin" in the database
- Login again to refresh the token

## Support

For issues or questions, please refer to the main project documentation or open an issue on the repository.
