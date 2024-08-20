const { fixture, matchesKeyboard, matchesMouse } = require('./helpers');

describe('<input type="range">', function() {
  beforeEach(function() {
    // Range inputs are super weird. Probably need to explore styling
    // the internal pseudo elements.
    // https://css-tricks.com/styling-cross-browser-compatible-range-inputs-css/
    return fixture('input-range.html');
  });

  it('should apply .focus-visible on keyboard focus', function() {
    return matchesKeyboard();
  });

  it('should NOT apply .focus-visible on mouse focus', function() {
    // Skip test in Microsoft Edge. It displays a modal UI on mouse click.
    if (process.env.TEST_BROWSER.includes('Edge')) {
      this.skip();
    } else {
      return matchesMouse(false);
    }
  });
});
