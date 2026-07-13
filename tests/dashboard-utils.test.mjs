import assert from 'node:assert/strict';
import test from 'node:test';

import { changeText, format, inActiveMarket, number, state } from '../dashboard-utils.js';
import { pageFromHash, pageIndexFromScroll } from '../dashboard-navigation.js';

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

test('horizontal page position is clamped to a valid page', () => {
  assert.equal(pageIndexFromScroll(0, 390, 5), 0);
  assert.equal(pageIndexFromScroll(780, 390, 5), 2);
  assert.equal(pageIndexFromScroll(9999, 390, 5), 4);
  assert.equal(pageIndexFromScroll(-200, 390, 5), 0);
  assert.equal(pageIndexFromScroll(100, 0, 5), 0);
});

test('legacy section hashes open the matching horizontal page', () => {
  assert.equal(pageFromHash('#command-center'), 'overview');
  assert.equal(pageFromHash('#candidates'), 'candidates');
  assert.equal(pageFromHash('#sector-strength'), 'sectors');
  assert.equal(pageFromHash('#risk-plan'), 'plan');
  assert.equal(pageFromHash('#notes'), 'review');
  assert.equal(pageFromHash('#unknown'), 'overview');
});

test('global market selection scopes market-dependent views', () => {
  state.activeMarket = 'US';
  assert.equal(inActiveMarket({ market: 'US' }), true);
  assert.equal(inActiveMarket({ market: 'JP' }), false);
  state.activeMarket = 'all';
  assert.equal(inActiveMarket({ market: 'JP' }), true);
});
