'use strict';

const { test } = require('node:test');
const assert = require('node:assert');
const { checkoutCart } = require('../src/checkout');
const { showBanner } = require('../src/banner');

const flagsOff = { hasFeature: () => false };
const flagsOn = { hasFeature: () => true };

test('legacy checkout prices discount lines when new_checkout is off', () => {
  const cart = { lines: [{ type: 'item', price: 100 }, { type: 'discount', price: -20 }] };
  assert.deepStrictEqual(checkoutCart(cart, flagsOff), { total: 80, via: 'legacy' });
});

test('new checkout throws on discount lines when new_checkout is on (demo bug)', () => {
  const cart = { lines: [{ type: 'item', price: 100 }, { type: 'discount', price: -20 }] };
  assert.throws(() => checkoutCart(cart, flagsOn), /cannot price discount lines/);
});

test('new checkout works on plain carts when new_checkout is on', () => {
  const cart = { lines: [{ type: 'item', price: 100 }] };
  assert.deepStrictEqual(checkoutCart(cart, flagsOn), { total: 100, via: 'new' });
});

test('banner shows only when old_banner is on', () => {
  assert.strictEqual(showBanner(flagsOn), 'Winter sale - 20% off!');
  assert.strictEqual(showBanner(flagsOff), null);
});
