# Security Advisories

## CVE-2025-66478 (React2Shell) - Remote Code Execution

**Severity**: Critical (CVSS 10.0)  
**Affected Versions**: Keep v0.45.12 and earlier (Next.js < 15.3.6)  
**Fixed in**: v0.45.13 (pending release)  

### Description
A critical vulnerability in React Server Components (RSC) affects Next.js applications. An unauthenticated attacker can send malicious HTTP requests to RSC endpoints, triggering unsafe deserialization and leading to remote code execution with Node.js process privileges.

### Impact
- Unauthenticated remote code execution
- Affects all Keep deployments with UI exposed to the internet
- Actively exploited in the wild (cryptominers, web shells)

### Mitigation
**Upgrade Keep to v0.45.13 or later immediately.**

For detailed information, see:
- https://nextjs.org/blog/CVE-2025-66478
- https://react.dev/blog/2025/12/02/critical-security-vulnerability
- https://react2shell.com

## Closes
Closes #5489
