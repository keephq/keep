const {
  fixture,
  matchesKeyboard,
  matchesMouse,
  FOCUS_RING_STYLE
} = require('./helpers');
const { Key, By } = require('selenium-webdriver');
const expect = require('expect');
const driver = global.__driver;

describe('keydown should always update focus-visible', function() {
  beforeEach(function() {
    return fixture('tabindex-zero.html');
  });

  it('should apply .focus-visible to the activeElement if a key is pressed', async function() {
    let body = await driver.findElement(By.css('body'));
    let el = await driver.findElement(By.css('#el'));
    await body.click();
    await el.click();
    await el.sendKeys(Key.SHIFT);
    let actual = await driver.executeScript(`
      return window.getComputedStyle(document.querySelector('#el')).outlineColor
    `);
    expect(actual).toEqual(FOCUS_RING_STYLE);
  });
});
