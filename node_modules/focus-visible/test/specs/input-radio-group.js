const {
  fixture,
  matchesKeyboard,
  matchesMouse,
  FOCUS_RING_STYLE
} = require('./helpers');
const { Key, By } = require('selenium-webdriver');
const expect = require('expect');
const driver = global.__driver;

describe('<input type="radio"> group', function() {
  beforeEach(function() {
    return fixture('input-radio-group.html');
  });

  it('should apply .focus-visible on keyboard focus', async function() {
    let body = await driver.findElement(By.css('body'));
    let first = await driver.findElement(By.css('#first'));
    let last = await driver.findElement(By.css('#last'));
    await first.click();
    await first.sendKeys(Key.ARROW_DOWN);
    let actual = await driver.executeScript(`
      return window.getComputedStyle(document.querySelector('#last')).outlineColor
    `);
    expect(actual).toEqual(FOCUS_RING_STYLE);
  });

  it('should NOT apply .focus-visible on mouse focus', async function() {
    let body = await driver.findElement(By.css('body'));
    let first = await driver.findElement(By.css('#first'));
    await first.click();
    let actual = await driver.executeScript(`
      return window.getComputedStyle(document.querySelector('#first')).outlineColor
    `);
    expect(actual).toNotEqual(FOCUS_RING_STYLE);
  });
});
