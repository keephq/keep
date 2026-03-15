
import * as jwt from 'jsonwebtoken';

const KEEP_JWT_SECRET = 'jwtsecret';

export function generateJwt(email: string, tenantId: string, role: string): string {
  const payload = {
    email: email,
    tenant_id: tenantId,
    role: role,
    exp: Math.floor(Date.now() / 1000) + (60 * 60 * 24), // 24 hours
  };

  return jwt.sign(payload, KEEP_JWT_SECRET, { algorithm: 'HS256' });
}
