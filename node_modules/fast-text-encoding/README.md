[![Test](https://github.com/samthor/fast-text-encoding/actions/workflows/node.js.yml/badge.svg)](https://github.com/samthor/fast-text-encoding/actions/workflows/node.js.yml)

This is a fast polyfill for [`TextEncoder`][1] and [`TextDecoder`][2], which let you encode and decode JavaScript strings into UTF-8 bytes.

It is fast partially as it does not support^ any encodings aside UTF-8 (and note that natively, only `TextDecoder` supports alternative encodings anyway).
See [some benchmarks](https://github.com/samthor/fast-text-encoding/tree/master/bench).

^If this polyfill used on Node v5.1 through v11 (when `Text...` was introduced), then this simply wraps `Buffer`, which supports many encodings and is native code.

[1]: https://developer.mozilla.org/en-US/docs/Web/API/TextEncoder
[2]: https://developer.mozilla.org/en-US/docs/Web/API/TextDecoder

# Usage

Install as "fast-text-encoding" via your favourite package manager.

You only need this polyfill if you're supporting older browsers like IE, legacy Edge, ancient Chrome and Firefox, or Node before v11.

## Browser

Include the minified code inside a `<script>` tag or as an ES6 Module for its side effects.
It will create `TextEncoder` and `TextDecoder` if the symbols are missing on `window` or `global.`

```html
<script src="node_modules/fast-text-encoding/text.min.js"></script>
<script type="module">
  import './node_modules/fast-text-encoding/text.min.js';
  import 'fast-text-encoding';  // or perhaps this
  // confidently do something with TextEncoder or TextDecoder \o/
</script>
```

⚠️ You'll probably want to depend on "text.min.js", as it's compiled to ES5 for older environments.

## Not Including Polyfill

If your project doesn't need the polyfill, but is included as a transitive dependency, we publish [an empty version](https://www.npmjs.com/package/fast-text-encoding/v/0.0.0-empty) that you could pin NPM or similar's version algorithm to.
Use "fast-text-encoding@empty".
