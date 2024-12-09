function dec2hex(dec: number) {
  return ("0" + dec.toString(16)).substring(-2);
}

export function generateRandomString() {
  var array = new Uint32Array(56 / 2);
  window.crypto.getRandomValues(array);
  return Array.from(array, dec2hex).join("");
}

export function sha256(plain: string) {
  const encoder = new TextEncoder();
  const data = encoder.encode(plain);
  return window.crypto.subtle.digest("SHA-256", data);
}

export function base64urlencode(a: ArrayBuffer) {
  var str = "";
  var bytes = new Uint8Array(a);
  var len = bytes.byteLength;
  for (var i = 0; i < len; i++) {
    str += String.fromCharCode(bytes[i]);
  }
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
