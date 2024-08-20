const { fixture, matchesKeyboard, matchesMouse } = require('./helpers');

describe('<input type="file">', function() {
  beforeEach(function() {
    // File input are weird...
    return fixture('input-file.html');
  });

  it('should apply .focus-visible on keyboard focus', function() {
    if (process.env.TEST_BROWSER.includes('Firefox')) {
      this.skip();
    } else {
      return matchesKeyboard();
    }
  });

  // Note: Skipping this test (though it currently passes) because it opens
  // a file chooser dialog and I don't want it interfering with other tests.
  it.skip('should NOT apply .focus-visible on mouse focus', function() {
    return matchesMouse(false);
  });
});
