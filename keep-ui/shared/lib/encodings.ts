/**
 * Converts a decimal number to a hexadecimal string with proper padding
 *
 * @param dec - The decimal number to convert
 * @returns A hexadecimal string representation
 * @internal This is a utility function used by generateRandomString
 */
function dec2hex(dec: number) {
  return ("0" + dec.toString(16)).substring(-2);
}

/**
 * Generates a cryptographically secure random string
 *
 * @returns A random hexadecimal string of 56 characters
 *
 * @example
 * const randomStr = generateRandomString();
 * // e.g. "7b8d4f2e9a1c6b3d5e8f2a7c9b4d1e6f3a8c5b2d7e9f1a3c8b6d4e7f2a9c5"
 */
export function generateRandomString() {
  var array = new Uint32Array(56 / 2);
  window.crypto.getRandomValues(array);
  return Array.from(array, dec2hex).join("");
}

/**
 * Generates a PKCE verifier string with length 128 characters
 *
 * @returns a random string of 128 characters
 *
 * @example
 * const verifier = generatePkceVerifier();
 * // e.g. "7b8d4f2e9a1c6b3d5e8f2a7c9b4d1e6f3a8c5b2d7e9f1a3c8b6d4e7f2a9c5"
 */
export function generatePkceVerifier(): string {
  const arr = new Uint8Array(96);
  window.crypto.getRandomValues(arr);
  return btoa(String.fromCharCode(...arr))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

/**
 * Computes the SHA-256 hash of a string
 *
 * @param plain - The input string to hash
 * @returns A Promise that resolves to an ArrayBuffer containing the hash
 *
 * @example
 * const hashBuffer = await sha256("hello world");
 */
export function sha256(plain: string) {
  const encoder = new TextEncoder();
  const data = encoder.encode(plain);
  return window.crypto.subtle.digest("SHA-256", data);
}

/**
 * Encodes an ArrayBuffer to base64url format (URL-safe base64)
 *
 * Base64url encoding is a variant of base64 that is URL and filename safe:
 * - Replaces '+' with '-'
 * - Replaces '/' with '_'
 * - Removes padding '=' characters
 *
 * @param a - The ArrayBuffer to encode
 * @returns The base64url-encoded string
 *
 * @example
 * const hashBuffer = await sha256("hello world");
 * const base64urlStr = base64urlencode(hashBuffer);
 */
export function base64urlencode(a: ArrayBuffer) {
  var str = "";
  var bytes = new Uint8Array(a);
  var len = bytes.byteLength;
  for (var i = 0; i < len; i++) {
    str += String.fromCharCode(bytes[i]);
  }
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
