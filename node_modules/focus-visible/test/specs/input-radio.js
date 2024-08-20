const { fixture, matchesKeyboard, matchesMouse } = require('./helpers');

describe('<input type="radio">', function() {
  beforeEach(function() {
    return fixture('input-radio.html');
  });

  it('should apply .focus-visible on keyboard focus', function() {
    return matchesKeyboard();
  });

  it('should NOT apply .focus-visible on mouse focus', function() {
    return matchesMouse(false);
  });
});
