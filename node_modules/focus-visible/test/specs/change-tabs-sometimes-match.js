const {
  fixture,
  matchesKeyboard,
  matchesMouse,
  FOCUS_RING_STYLE
} = require('./helpers');
const { Key, By } = require('selenium-webdriver');
const expect = require('expect');
const driver = global.__driver;

describe.skip('change tabs, only match if elements had focus-visible', function() {
  beforeEach(function() {
    // Note: For focus to enter the page properly with this fixture I had
    // to make sure the div had some width/height.
    // This seems like a geckodriver bug.
    return fixture('change-tabs-sometimes-match.html');
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

  it('should NOT retain .focus-visible if the user switches tabs and an element did not have .focus-visible because it was mouse focused', async function() {
    let el = await driver.findElement(By.css('#el'));
    await el.click();
    await driver.sleep(4000);
    let actual = await driver.executeScript(`
      return window.getComputedStyle(document.querySelector('#el')).outlineColor
    `);
    expect(actual).toNotEqual(FOCUS_RING_STYLE);
  });
});
