const { fixture, matchesKeyboard, matchesMouse } = require('./helpers');

describe('<input type="checkbox">', function() {
  beforeEach(function() {
    return fixture('input-checkbox.html');
  });

  it('should apply .focus-visible on keyboard focus', function() {
    return matchesKeyboard();
  });

  it('should NOT apply .focus-visible on mouse focus', function() {
    return matchesMouse(false);
  });
});
