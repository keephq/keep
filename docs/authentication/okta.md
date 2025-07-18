# Okta Integration Guide

This document provides comprehensive information about the Okta integration in Keep, including configuration, deployment, maintenance, and testing.

## Overview

Keep supports Okta as an authentication provider, enabling:
- Single Sign-On (SSO) via Okta
- JWT token validation with JWKS
- User and group management through Okta
- Role-based access control
- Token refresh capabilities

## Environment Variables

### Backend Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AUTH_TYPE` | Set to `"okta"` to enable Okta authentication | `okta` |
| `OKTA_DOMAIN` | Your Okta domain | `company.okta.com` |
| `OKTA_API_TOKEN` | Admin API token for Okta management | `00aBcD3f4GhIJkl5m6NoPQr` |
| `OKTA_ISSUER` | The issuer URL for your Okta application | `https://company.okta.com/oauth2/default` |
| `OKTA_CLIENT_ID` | Client ID of your Okta application | `0oa1b2c3d4e5f6g7h8i9j` |
| `OKTA_CLIENT_SECRET` | Client Secret of your Okta application | `abcd1234efgh5678ijkl9012` |
| `OKTA_AUDIENCE` | (Optional) The audience for token validation | `api://keep` |

### Frontend Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AUTH_TYPE` | Set to `"OKTA"` to enable Okta authentication | `OKTA` |
| `OKTA_CLIENT_ID` | Client ID of your Okta application | `0oa1b2c3d4e5f6g7h8i9j` |
| `OKTA_CLIENT_SECRET` | Client Secret of your Okta application | `abcd1234efgh5678ijkl9012` |
| `OKTA_ISSUER` | The issuer URL for your Okta application | `https://company.okta.com/oauth2/default` |
| `OKTA_DOMAIN` | Your Okta domain | `company.okta.com` |

## Okta Configuration

### Creating an Okta Application

1. Sign in to your Okta Admin Console
2. Navigate to **Applications** > **Applications**
3. Click **Create App Integration**
4. Select **OIDC - OpenID Connect** as the Sign-in method
5. Choose **Web Application** as the Application type
6. Click **Next**

### Application Settings

1. **Name**: Enter a name for your application (e.g., "Keep")
2. **Grant type**: Select Authorization Code
3. **Sign-in redirect URIs**: Enter your app's callback URL, e.g., `https://your-keep-domain.com/api/auth/callback/okta`
4. **Sign-out redirect URIs**: Enter your app's sign-out URL, e.g., `https://your-keep-domain.com/signin`
5. **Assignments**:
   - **Skip group assignment for now** or assign to appropriate groups
6. Click **Save**

### Create API Token

1. Navigate to **Security** > **API**
2. Select the **Tokens** tab
3. Click **Create Token**
4. Name your token (e.g., "Keep Integration")
5. Copy the generated token value (this will be your `OKTA_API_TOKEN`)

### Configure OIDC Claims (Optional but Recommended)

1. Navigate to your application
2. Go to the **Sign On** tab
3. Under **OpenID Connect ID Token**, click **Edit**
4. Add custom claims:
   - `keep_tenant_id`: The tenant ID in Keep
   - `keep_role`: The user's role in Keep

## Deployment Instructions

### Docker Deployment

Add the required environment variables to your docker-compose file or Kubernetes deployment:

```yaml
environment:
  - AUTH_TYPE=okta
  - OKTA_DOMAIN=your-company.okta.com
  - OKTA_API_TOKEN=your-api-token
  - OKTA_ISSUER=https://your-company.okta.com/oauth2/default
  - OKTA_CLIENT_ID=your-client-id
  - OKTA_CLIENT_SECRET=your-client-secret
```

### Next.js Frontend

Configure environment variables in your `.env.local` file:

```
AUTH_TYPE=OKTA
OKTA_CLIENT_ID=your-client-id
OKTA_CLIENT_SECRET=your-client-secret
OKTA_ISSUER=https://your-company.okta.com/oauth2/default
OKTA_DOMAIN=your-company.okta.com
```

### Vercel Deployment

Add the environment variables in your Vercel project settings.

## User and Group Management

### Users

The system automatically maps Okta users to Keep users. Key mappings:

- Okta email → Keep email
- Okta firstName → Keep name
- Okta groups → Keep groups
- Custom claim `keep_role` → Keep role (defaults to "user" if not specified)

### Groups

Groups in Okta are synchronized with Keep. Groups with names starting with `keep_` are treated as roles.

### Roles

Roles are implemented as Okta groups with the prefix `keep_`. For example:
- `keep_admin` → Admin role in Keep
- `keep_user` → User role in Keep

## Authentication Flow

1. User accesses Keep application
2. User is redirected to Okta login page
3. After successful authentication, Okta returns an ID token and access token
4. Keep validates the token using Okta's JWKS endpoint
5. Keep extracts user information and permissions from the token
6. When tokens expire, Keep automatically refreshes them using the refresh token

## Token Refresh

The refresh token flow is handled automatically by the application:

1. The system detects when an access token is about to expire
2. It uses the refresh token to obtain a new access token from Okta
3. The new token is stored and used for subsequent requests

## Testing Strategies

### Unit Tests

1. **AuthVerifier Tests**: Test token validation with mock tokens
   ```python
   def test_okta_verify_bearer_token():
       # Create a mock token with the expected claims
       # Initialize the OktaAuthVerifier
       # Verify the token is validated correctly
   ```

2. **IdentityManager Tests**: Test user and group management
   ```python
   def test_okta_create_user():
       # Mock Okta API responses
       # Test creating a user
       # Verify the correct API calls are made
   ```

### Integration Tests

1. **End-to-End Authentication Flow**:
   - Create a test user in Okta
   - Attempt to log in to the application
   - Verify successful authentication

2. **Token Refresh Test**:
   - Obtain an access token and refresh token
   - Wait for token expiration
   - Verify token refresh occurs automatically

3. **Role-Based Access Control**:
   - Create users with different roles
   - Verify access to different endpoints based on roles

### Load Tests

1. **Token Validation Performance**:
   - Simulate multiple concurrent requests with tokens
   - Measure response time and system load
   - Verify JWKS caching is working correctly

2. **User Management Scaling**:
   - Test with a large number of users and groups
   - Measure performance of group and user operations

## Troubleshooting

### Common Issues

1. **Invalid Token Errors**:
   - Check that `OKTA_ISSUER` matches the issuer in your Okta application
   - Verify that token signing algorithm (RS256) is supported
   - Check for clock skew between your server and Okta

2. **API Request Failures**:
   - Verify that `OKTA_API_TOKEN` is valid and has sufficient permissions
   - Check rate limiting on Okta API

3. **User Not Found**:
   - Verify that the user exists in Okta
   - Check user status (active/deactivated)

### Debugging

1. Enable debug logging:
   ```
   AUTH_DEBUG=true
   ```

2. Check Okta API logs in the Okta Admin Console

## Maintenance Considerations

### Token Rotation

- Rotate the `OKTA_API_TOKEN` periodically for security
- Update the application with the new token without downtime

### JWKS Caching

- The implementation caches JWKS keys for 24 hours
- Adjust the cache duration if needed based on key rotation policy

### Custom Claims

- When adding new custom claims, update both Okta configuration and code

### API Rate Limits

- Be aware of Okta API rate limits
- Implement retry logic for rate limit errors

## Code Structure

### Backend Components

- **`keep/identitymanager/identity_managers/okta/okta_authverifier.py`**: Handles JWT validation with JWKS
- **`keep/identitymanager/identity_managers/okta/okta_identitymanager.py`**: Manages users, groups, and roles via Okta API

### Frontend Components

- **`auth.config.ts`**: NextAuth.js configuration for Okta
- **`authenticationType.ts`**: Defines Okta as an authentication type

## Security Considerations

1. **Secure Storage of Secrets**:
   - Store `OKTA_CLIENT_SECRET` and `OKTA_API_TOKEN` securely
   - Never commit secrets to version control

2. **Token Validation**:
   - Always validate tokens with proper signature verification
   - Verify token audience and issuer

3. **Scoped API Tokens**:
   - Use the principle of least privilege for API tokens

## Future Improvements

1. **Enhanced Group Mapping**:
   - Implement more sophisticated group-to-role mappings
   - Support nested groups in Okta

2. **Custom Authorization Servers**:
   - Support multiple Okta authorization servers
   - Allow tenant-specific authorization servers

3. **Custom Scope Handling**:
   - Better integrate Okta scopes with Keep permissions

## Support and Resources

- [Okta Developer Documentation](https://developer.okta.com/docs/reference/)
- [NextAuth.js Okta Provider Documentation](https://next-auth.js.org/providers/okta)
- [JWT Debugging Tools](https://jwt.io/) 