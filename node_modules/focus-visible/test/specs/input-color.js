const { fixture, matchesKeyboard, matchesMouse } = require('./helpers');

describe('<input type="color">', function() {
  beforeEach(function() {
    return fixture('input-color.html');
  });

  it('should apply .focus-visible on keyboard focus', function() {
    return matchesKeyboard();
  });

  // Note: Skipping this test (though it currently passes) because it opens
  // a color picker dialog and I don't want it interfering with other tests.
  it.skip('should NOT apply .focus-visible on mouse focus', function() {
    return matchesMouse(false);
  });
});
