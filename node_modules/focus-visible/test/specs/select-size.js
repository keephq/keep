const { fixture, matchesKeyboard, matchesMouse } = require('./helpers');

describe('<select size="3">', function() {
  beforeEach(function() {
    return fixture('select-size.html');
  });

  it('should apply .focus-visible on keyboard focus', function() {
    return matchesKeyboard();
  });

  it('should NOT apply .focus-visible on mouse focus', function() {
    return matchesMouse(false);
  });
});
