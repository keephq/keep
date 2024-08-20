const {
  fixture,
  matchesKeyboard,
  matchesMouse,
  FOCUS_RING_STYLE
} = require('./helpers');
const { Key, By } = require('selenium-webdriver');
const expect = require('expect');
const driver = global.__driver;

describe('<div contenteditable>', function() {
  beforeEach(function() {
    return fixture('contenteditable.html');
  });

  // FF won't focus a div with contenteditable if it's the first element on the page.
  // So we click on a dummy element to move focus into the document.
  it('should apply .focus-visible on keyboard focus', async function() {
    let start = await driver.findElement(By.css('#start'));
    await start.click();
    await start.sendKeys(Key.TAB);
    let actual = await driver.executeScript(`
      return window.getComputedStyle(document.querySelector('#el')).outlineColor
    `);
    expect(actual).toEqual(FOCUS_RING_STYLE);
  });

  it('should apply .focus-visible on mouse focus', async function() {
    return matchesMouse();
  });
});
