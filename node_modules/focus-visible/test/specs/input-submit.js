const { fixture, matchesKeyboard, matchesMouse } = require('./helpers');

describe('<input type="submit">', function() {
  beforeEach(function() {
    return fixture('input-submit.html');
  });

  it('should apply .focus-visible on keyboard focus', function() {
    return matchesKeyboard();
  });

  it('should NOT apply .focus-visible on mouse focus', function() {
    return matchesMouse(false);
  });
});
