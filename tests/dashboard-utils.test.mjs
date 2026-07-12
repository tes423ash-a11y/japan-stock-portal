import assert from 'node:assert/strict';
import test from 'node:test';

import { changeText, format, number } from '../dashboard-utils.js';

test('missing numeric values stay missing instead of becoming zero', () => {
  assert.equal(number(null), null);
  assert.equal(number(undefined), null);
  assert.equal(number(''), null);
  assert.equal(number('  '), null);
  assert.equal(format(null), '-');
  assert.equal(changeText(null), '-');
});

test('real zero values remain valid numbers', () => {
  assert.equal(number(0), 0);
  assert.equal(number('0'), 0);
  assert.equal(format(0), '0');
});
