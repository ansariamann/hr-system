# HR System Authentication & Portal Access

## Overview

The HR System now has **separate login portals** for Admin/HR staff and Clients, with proper authentication and role-based access control.

## Login Portals

### 1. Admin/HR Portal Login

- **URL**: `/admin/login`
- **Access**: Internal HR staff and recruiters
- **Features**: Full candidate management, talent pool, blacklisting, SSE events
- **After Login**: Redirects to `/hr/dashboard`

### 2. Client Portal Login

- **URL**: `/client/login`
- **Access**: External clients reviewing candidates
- **Features**: Kanban board, interview scheduling, offer management
- **After Login**: Redirects to `/portal/dashboard`

## Demo Credentials

### Admin/HR User

```
Email: admin@example.com
Password: admin123
```

### Client User

```
Email: client@example.com
Password: client123
```

## Architecture

### Authentication Flow

1. **Login Pages** (`AdminLogin.jsx`, `ClientLogin.jsx`)
   - Separate branded login experiences
   - Role-specific UI theming
   - Form validation and error handling

2. **Auth Context** (`AuthContext.jsx`)
   - Manages authentication state across the app
   - Stores JWT tokens in localStorage
   - Provides `useAuth()` hook for components
   - Auto-restores session on page refresh

3. **Protected Routes** (`ProtectedRoute.jsx`)
   - Wraps authenticated pages
   - Enforces role-based access (admin vs client)
   - Redirects unauthenticated users to appropriate login
   - Shows loading state during auth verification

4. **API Integration** (`api.js`)
   - `api.login(email, password)` - Authenticates against backend
   - Fallback to demo credentials when backend offline
   - Token management (storage, retrieval, clearing)
   - Auto-includes Bearer token in API requests

### Route Structure

```
/admin/login              → Admin login page
/client/login             → Client login page
/hr/dashboard             → Protected HR portal (admin only)
/portal/dashboard         → Protected Client portal (client only)
/                         → Redirects to /admin/login
```

### Component Hierarchy

```
App.jsx (Root)
├── BrowserRouter
│   └── AuthProvider (Context wrapper)
│       ├── Public Routes
│       │   ├── /admin/login → AdminLogin
│       │   └── /client/login → ClientLogin
│       └── Protected Routes
│           ├── /hr/dashboard → ProtectedRoute(admin) → HrPortalView
│           └── /portal/dashboard → ProtectedRoute(client) → ClientPortalView
```

## Backend Integration

### Expected Backend Endpoints

```
POST /api/v1/auth/login
{
  "email": "admin@example.com",
  "password": "admin123"
}

Response:
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "userId": "user-123",
  "email": "admin@example.com",
  "role": "ADMIN"
}
```

### Roles

- `ADMIN` - HR staff with full system access
- `CLIENT` - External clients with limited access

### Token Storage

- JWT token stored in `localStorage` as `ats_auth_token`
- User info stored as `user` object
- Auto-cleared on logout or 401 responses

## Security Features

1. **Role-Based Access Control (RBAC)**
   - Admin routes reject client users
   - Client routes reject admin users
   - Proper separation of concerns

2. **Token Management**
   - Automatic token inclusion in API headers
   - Token expiry handling (401 → redirect to login)
   - Secure storage in localStorage

3. **Route Protection**
   - All sensitive routes wrapped in `ProtectedRoute`
   - Unauthenticated access blocked
   - Loading states prevent flashing

4. **Session Persistence**
   - User stays logged in across page refreshes
   - Auth state restored from localStorage
   - Logout clears all session data

## Usage Examples

### Using Auth in Components

```jsx
import { useAuth } from "../contexts/AuthContext";

function MyComponent() {
  const { user, isAdmin, isClient, logout } = useAuth();

  return (
    <div>
      <p>Welcome {user?.email}</p>
      {isAdmin && <p>You have admin access</p>}
      <button onClick={logout}>Sign Out</button>
    </div>
  );
}
```

### Creating Protected Routes

```jsx
<Route
  path="/admin-only-page"
  element={
    <ProtectedRoute requireAdmin>
      <AdminOnlyComponent />
    </ProtectedRoute>
  }
/>
```

### Manual API Calls with Auth

```jsx
import { api } from "./api";

// Login
const result = await api.login("admin@example.com", "admin123");

// Logout
await api.logout();
```

## Styling

- Login pages use dedicated `Login.css` stylesheet
- Theme variants: `.login-container` (admin), `.login-container.client-theme` (client)
- Responsive design (mobile-friendly)
- Glassmorphism effects and gradients
- Brand-consistent color schemes

## Development Notes

### When Backend is Offline

- Falls back to demo credentials (see above)
- Mock JWT tokens generated
- Local candidate data used
- Full UI functionality maintained

### Adding New Protected Routes

1. Define route in `App.jsx`
2. Wrap element with `<ProtectedRoute>`
3. Specify `requireAdmin` or `requireClient` prop
4. Component automatically gets auth context

### Extending Auth System

- Add new roles in `AuthContext.jsx`
- Update `ProtectedRoute.jsx` role checks
- Modify backend `/auth/login` endpoint
- Add role-specific UI logic

## Migration from Previous Version

### What Changed

- **Before**: Direct access to `/` and `/portal` without authentication
- **After**: Login required, role-based routing

### Breaking Changes

- Root `/` now redirects to `/admin/login`
- Direct URL access blocked without valid session
- Need to login before accessing any portal

### Update Steps for Existing Deployments

1. Ensure backend `/auth/login` endpoint is live
2. Deploy new frontend build
3. Clear localStorage to reset sessions
4. Users must re-login on first access

## Troubleshooting

### "Invalid credentials" error

- Check email/password match demo credentials
- Verify backend `/auth/login` endpoint is accessible
- Check browser console for API errors

### Infinite redirect loop

- Clear localStorage and cookies
- Check `AuthContext` initialization
- Verify token format in backend response

### 401 Unauthorized on API calls

- Token may have expired
- Backend may be rejecting token format
- Check `Authorization: Bearer <token>` header

### Can't access portal after login

- Check user role matches route requirement
- Verify `ProtectedRoute` props
- Review console for role mismatch errors

## Future Enhancements

- [ ] Password reset flow
- [ ] Remember me functionality
- [ ] Multi-factor authentication (MFA)
- [ ] Session timeout warnings
- [ ] OAuth2 integration (Google, Microsoft)
- [ ] Role management UI
- [ ] Audit logs for login attempts
- [ ] IP-based access restrictions
