const { fixture, matchesKeyboard, matchesMouse } = require('./helpers');

describe('<button>', function() {
  beforeEach(function() {
    return fixture('button.html');
  });

  it('should apply .focus-visible on keyboard focus', function() {
    return matchesKeyboard();
  });

  it('should NOT apply .focus-visible on mouse focus', function() {
    return matchesMouse(false);
  });
});
