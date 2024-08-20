const { Key, By } = require('selenium-webdriver');
const {
  FOCUS_RING_STYLE,
  fixture,
  matchesKeyboard,
  matchesMouse
} = require('./helpers');
const expect = require('expect');

async function shadowDescendantMatchesKeyboard(shouldMatch = true) {
  let driver = global.__driver;
  let body = await driver.findElement(By.css('body'));
  await body.sendKeys(Key.TAB);
  let actual = await driver.executeScript(`
    var el = document.querySelector('#el');
    var shadowDescendant = el.shadowRoot.querySelector('#shadow-el');
    return window.getComputedStyle(shadowDescendant).outlineColor;
  `);
  if (shouldMatch) {
    expect(actual).toEqual(FOCUS_RING_STYLE);
  } else {
    expect(actual).toNotEqual(FOCUS_RING_STYLE);
  }
}

async function shadowDescendantMatchesMouse(shouldMatch = true) {
  let driver = global.__driver;
  let element = await driver.executeScript(`
    return document.querySelector('#el').shadowRoot.querySelector('#shadow-el');
  `);
  await element.click();
  let actual = await driver.executeScript(`
    return window.getComputedStyle(document.querySelector('#el')
        .shadowRoot.querySelector('#shadow-el')).outlineColor;
  `);
  if (shouldMatch) {
    expect(actual).toEqual(FOCUS_RING_STYLE);
  } else {
    expect(actual).toNotEqual(FOCUS_RING_STYLE);
  }
}

describe('ShadowDOM', function() {
  beforeEach(function() {
    return fixture('shadow-dom.html');
  });

  it('should apply .focus-visible on keyboard focus', async function() {
    return matchesKeyboard();
  });

  it('should NOT apply .focus-visible on mouse focus', function() {
    return matchesMouse(false);
  });

  describe('focusable elements in shadow', () => {
    it('should apply .focus-visible on keyboard focus', () => {
      return shadowDescendantMatchesKeyboard();
    });

    it('should NOT apply .focus-visible on mouse focus', function() {
      return shadowDescendantMatchesMouse(false);
    });
  });
});
