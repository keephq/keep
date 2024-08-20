const {
  fixture,
  matchesKeyboard,
  matchesMouse,
  FOCUS_RING_STYLE
} = require('./helpers');
const { Key, By } = require('selenium-webdriver');
const expect = require('expect');
const driver = global.__driver;

describe('using a pointing device to click an element after being in keyboard modality', function() {
  beforeEach(function() {
    return fixture('pointer-turns-off-keyboard.html');
  });

  it('should NOT apply .focus-visible if a pointer is used after a keyboard press on an already focused element', async function() {
    let body = await driver.findElement(By.css('body'));
    let el = await driver.findElement(By.css('#el'));
    let other = await driver.findElement(By.css('#other'));
    await body.click();
    await body.sendKeys(Key.TAB);
    await body.sendKeys(Key.TAB);
    // Because the element is already focused, we don't get a focus event here
    // but we _do_ get a keydown event. Normally we clear the hadKeyboardEvent
    // flag after the focus event is handled, but since there wasn't one, we
    // still think we're in keyboard modality.
    await other.sendKeys(Key.SPACE);
    // Using a pointing device should force keyboard modality off.
    await el.click();
    let actual = await driver.executeScript(`
      return window.getComputedStyle(document.querySelector('#el')).outlineColor
    `);
    expect(actual).toNotEqual(FOCUS_RING_STYLE);
  });
});
