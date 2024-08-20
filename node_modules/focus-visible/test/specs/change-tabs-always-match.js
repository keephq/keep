const {
  fixture,
  matchesKeyboard,
  matchesMouse,
  FOCUS_RING_STYLE
} = require('./helpers');
const { Key, By } = require('selenium-webdriver');
const expect = require('expect');
const driver = global.__driver;

describe.skip('change tabs, always match if elements should always have focus-visible', function() {
  beforeEach(function() {
    return fixture('change-tabs-always-match.html');
  });

  it('should retain .focus-visible if the user switches tabs and an element had .focus-visible from keyboard', async function() {
    let body = await driver.findElement(By.css('body'));
    let el = await driver.findElement(By.css('#el'));
    await body.click();
    await body.sendKeys(Key.TAB);
    await el.sendKeys(Key.SPACE);
    await driver.sleep(4000); // sleep while we open and close a new tab.
    let actual = await driver.executeScript(`
      return window.getComputedStyle(document.querySelector('#el')).outlineColor
    `);
    expect(actual).toEqual(FOCUS_RING_STYLE);
  });

  it('should retain .focus-visible if the user switches tabs and an element had .focus-visible from mouse', async function() {
    let el = await driver.findElement(By.css('#el'));
    await el.click();
    await driver.sleep(4000);
    let actual = await driver.executeScript(`
      return window.getComputedStyle(document.querySelector('#el')).outlineColor
    `);
    expect(actual).toEqual(FOCUS_RING_STYLE);
  });
});
