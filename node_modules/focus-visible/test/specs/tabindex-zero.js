const { fixture, matchesKeyboard, matchesMouse } = require('./helpers');

describe('[tabindex=0]', function() {
  beforeEach(function() {
    // Note: For focus to enter the page properly with this fixture I had
    // to make sure the div had some width/height.
    // This seems like a geckodriver bug.
    return fixture('tabindex-zero.html');
  });

  it('should apply .focus-visible on keyboard focus', function() {
    return matchesKeyboard();
  });

  it('should NOT apply .focus-visible on mouse focus', function() {
    return matchesMouse(false);
  });
});
