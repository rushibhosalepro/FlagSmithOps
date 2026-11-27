'use strict';

// Broken feature: new one-page checkout behind the `new_checkout` flag.
// Incident drill: "Checkout is failing in production" -> the kill switch
// is the `new_checkout` flag in the Production environment.

function newCheckout(cart) {
  for (const line of cart.lines) {
    if (line.type === 'discount') {
      // Known demo bug: the new checkout cannot price discount lines.
      throw new Error('new checkout cannot price discount lines');
    }
  }
  return { total: sum(cart), via: 'new' };
}

function legacyCheckout(cart) {
  return { total: sum(cart), via: 'legacy' };
}

function sum(cart) {
  return cart.lines.reduce((total, line) => total + line.price, 0);
}

function checkoutCart(cart, flagsmith) {
  if (flagsmith.hasFeature('new_checkout')) {
    return newCheckout(cart);
  }
  return legacyCheckout(cart);
}

module.exports = { checkoutCart, newCheckout, legacyCheckout };
