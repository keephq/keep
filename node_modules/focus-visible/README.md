[![Build Status](https://travis-ci.org/WICG/focus-visible.svg?branch=main)](https://travis-ci.org/WICG/focus-visible)

Based on the proposed CSS
[`:focus-visible`](https://drafts.csswg.org/selectors-4/#the-focus-visible-pseudo)
pseudo-selector,
this prototype adds a `focus-visible` class to the focused element,
in situations in which the `:focus-visible` pseudo-selector should match.

# Details

- Read the [Explainer](explainer.md).
- Read the [Spec](https://drafts.csswg.org/selectors-4/#the-focus-visible-pseudo).
- Try the [Demo](https://wicg.github.io/focus-visible/demo).
- [Give feedback!](https://github.com/WICG/focus-visible/issues)
    - Open discussions:
        - [What's the impact on users with low vision or cognitive impairments?](https://github.com/WICG/focus-visible/issues/128)
        - [Should :focus-visible match when returning focus or programmatically focusing?](https://github.com/WICG/focus-visible/issues/88)
        - [Brainstorm: options for opting in to always matching focus ring.](https://github.com/WICG/focus-visible/issues/42)

# Polyfill

## Support

👋 `:focus-visible` is now [supported in all major browsers](https://developer.mozilla.org/en-US/docs/Web/CSS/:focus-visible#browser_compatibility).

![A browser suppor table showing focus-visible is supported in Chrome 86, Edge 86, Firefox 85, Opera 72, Safari 15.4, all Android browsers, Safari 15.4 on iOS, Android WebView, and Samsung Internet](https://user-images.githubusercontent.com/1066253/208977092-0fdacba7-b1de-4a8f-90f9-880b06dcdb26.png)

We would encourage you to use the CSS selector instead of this polyfill if you are able. We are not currently planning to make any updates or release new versions of the polyfill, but are open to discussion in GitHub issues if changes need to be made for emergencies.

## Installation

`npm install --save focus-visible`

_We recommend only using versions of the polyfill that have been published to npm, rather than
cloning the repo and using the source directly. This helps ensure the version you're using is stable
and thoroughly tested._

_If you do want to build from source, make sure you clone the latest tag!_

## Usage

### 1. Add the script to your page

```html
    ...
    <script src="/node_modules/focus-visible/dist/focus-visible.min.js"></script>
  </body>
</html>
```

### 2. Update your CSS

We suggest that users
selectively disable the default focus style
by selecting for the case when the polyfill is loaded
and `.focus-visible` is _not_ applied to the element:

```css
/*
  This will hide the focus indicator if the element receives focus via the mouse,
  but it will still show up on keyboard focus.
*/
.js-focus-visible :focus:not(.focus-visible) {
  outline: none;
}
```

If there are elements which should always have a focus ring shown,
authors may explicitly add the `focus-visible` class.
If explicitly added, it will not be removed on `blur`.

Alternatively, if you're using a framework which overwrites your classes ([#179](https://github.com/WICG/focus-visible/issues/179)),
you can rely on the `data-js-focus-visible` and `data-focus-visible-added` attributes.
```css
[data-js-focus-visible] :focus:not([data-focus-visible-added]) {
  outline: none;
}
```

### How it works

The script uses two heuristics to determine whether the keyboard is being (or will be) used:

- a `focus` event immediately following a `keydown` event where the key pressed was either `Tab`,
`Shift + Tab`, or an arrow key.

- focus moves into an element which requires keyboard interaction,
  such as a text field

  - NOTE: this means that HTML elements like `<input type={text|email|password|...}>` or `<textarea>` will **always** match the `:focus-visible` selector, regardless of whether they are focused via a keyboard or a mouse.

- _TODO: ideally, we also trigger keyboard modality
  following a keyboard event which activates an element or causes a mutation;
  this still needs to be implemented._

### Shadow DOM

It could be very expensive to apply this polyfill automatically to every shadow
root that is created in a given document, so the polyfill ignores shadow roots
by default. If you are using Shadow DOM in a component, it is possible to apply
this polyfill imperatively to the component's shadow root:

```javascript
// Check for the polyfill:
if (window.applyFocusVisiblePolyfill != null) {
  window.applyFocusVisiblePolyfill(myComponent.shadowRoot);
}
```

### Lazy-loading

When this polyfill is lazy-loaded, and you are applying the polyfill to a shadow
root with JavaScript, it is important to know when the polyfill has become
available before trying to use it.

In order to act at the right time, you can observe the global
`focus-visible-polyfill-ready` event:

```javascript
window.addEventListener('focus-visible-polyfill-ready',
    () => window.applyFocusVisiblePolyfill(myComponent.shadowRoot),
    { once:  true });
```

**Important:** this event is _only_ intended to support late application of the
polyfill in lazy-loading use cases. Do not write code that depends on the event
firing, as it is timing dependent and only fired once. If you plan to lazy-load
the polyfill, it is recommended that you check for it synchronously (see example
above under "Shadow DOM") and listen for the event only if the polyfill isn't
available yet.

# Backwards compatibility
Until all browsers ship `:focus-visible` developers will need to use it defensively to avoid accidentally
removing focus styles in legacy browsers. This is easy to do with the polyfill.

```css
/*
  This will hide the focus indicator if the element receives focus via the mouse,
  but it will still show up on keyboard focus.
*/
.js-focus-visible :focus:not(.focus-visible) {
  outline: none;
}

/*
  Optionally: Define a strong focus indicator for keyboard focus.
  If you choose to skip this step then the browser's default focus
  indicator will be displayed instead.
*/
.js-focus-visible .focus-visible {
  …
}
```

As [explained by the Paciello Group](https://developer.paciellogroup.com/blog/2018/03/focus-visible-and-backwards-compatibility/), developers who don't use the polyfill can still defensively rely on `:focus-visible` using the
following snippet:

```css
/*
  Provide basic, default focus styles.
*/
button:focus {
  …
}

/*
  Remove default focus styles for mouse users ONLY if
  :focus-visible is supported on this platform.
*/
button:focus:not(:focus-visible) {
  …
}

/*
  Optionally: If :focus-visible is supported on this
  platform, provide enhanced focus styles for keyboard
  focus.
*/
button:focus-visible {
  …
}
```

In the future, when all browsers support `:focus-visible`, the
snippets above will be unnecessary. But until that time it's important
to be mindful when you use `:focus-visible` and to ensure you always
have a fallback strategy.

### Big Thanks

Cross-browser Testing Platform and Open Source <3 Provided by [Sauce Labs][homepage]

<a href="https://saucelabs.com"><img src="https://i.imgur.com/f2cK9ZQ.jpg" width="200"></a>

[homepage]: https://saucelabs.com
