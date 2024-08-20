const { fixture, FOCUS_RING_STYLE } = require('./helpers');
const { Key, By } = require('selenium-webdriver');
const expect = require('expect');
const driver = global.__driver;

// IE11 has a strange behavior where it will always focus an <svg> on the page.
// This test is to verify that we don't hit an error in this situation.
// See https://github.com/WICG/focus-visible/issues/80#issuecomment-383424156.
describe('svg focus', function() {
  beforeEach(function() {
    return fixture('svg.html');
  });

  it('should NOT apply .focus-visible if a non-interactive SVG is keyboard focused', async function() {
    let actual;

    // Tells Selenium to keep sending Tabs until the end element is reached.
    async function tabUntil(body, end) {
      let activeId;
      let activeElement;

      while (true) {
        activeId = await driver.executeScript(
          `return document.activeElement.id`
        );

        if (activeId) {
          if (activeId === end) {
            break;
          }
          // Only IE11 will stop here and focus the #icon element.
          // If the element has focus, assert that :focus-visible has not been
          // applied to it.
          if (activeId === 'icon') {
            actual = await driver.executeScript(`
              return window.getComputedStyle(document.querySelector('#end')).outlineColor
            `);
            expect(actual).toNotEqual(FOCUS_RING_STYLE);
          }
          // Move focus to the next element.
          // IE11's selenium driver won't move focus if we send it to body again
          // so we need to send it to the activeElement.
          activeElement = await driver.findElement(By.css(`#${activeId}`));
          await activeElement.sendKeys(Key.TAB);
        } else {
          // Work around IE11 weirdness which sends focus to <html> first.
          await body.sendKeys(Key.TAB);
        }
      }
    }

    let body = await driver.findElement(By.css('body'));
    await body.click();
    // Tabs through the document until it reaches the last element.
    // In IE11 the non-interactive SVG, #icon will be focused.
    // If it throws, then the test will fail.
    await tabUntil(body, 'end');
    actual = await driver.executeScript(`
      return window.getComputedStyle(document.querySelector('#end')).outlineColor
    `);
    expect(actual).toEqual(FOCUS_RING_STYLE);
  });
});
