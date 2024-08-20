const {
  fixture,
  matchesKeyboard,
  matchesMouse,
  FOCUS_RING_STYLE
} = require('./helpers');
const { Key, By } = require('selenium-webdriver');
const expect = require('expect');
const driver = global.__driver;

describe('programmatic focus on element that should always match focus-visible', function() {
  beforeEach(function() {
    return fixture('programmatic-focus-always.html');
  });

  it('should apply .focus-visible if a keyboard press calls focus() and the element should always match', async function() {
    let body = await driver.findElement(By.css('body'));
    let start = await driver.findElement(By.css('#start'));
    await body.click();
    await body.sendKeys(Key.TAB);
    await start.sendKeys(Key.SPACE);
    let actual = await driver.executeScript(`
      return window.getComputedStyle(document.querySelector('#el')).outlineColor
    `);
    expect(actual).toEqual(FOCUS_RING_STYLE);
  });

  it('should apply .focus-visible if a mouse press calls focus() and the element should always match', async function() {
    let body = await driver.findElement(By.css('body'));
    let start = await driver.findElement(By.css('#start'));
    await start.click();
    let actual = await driver.executeScript(`
      return window.getComputedStyle(document.querySelector('#el')).outlineColor
    `);
    expect(actual).toEqual(FOCUS_RING_STYLE);
  });
});
