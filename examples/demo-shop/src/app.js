'use strict';

// Demo entry point. Works offline with a fake flag client that reads flags
// from the environment, and uses the real Flagsmith Node SDK when it is
// installed (npm install flagsmith-nodejs) and FLAGSMITH_ENV_KEY is set.
//
//   node src/app.js                       # offline, all flags off
//   FLAGS="new_checkout,old_banner" node src/app.js   # offline, flags on

const { checkoutCart } = require('./checkout');
const { showBanner } = require('./banner');

function fakeClient() {
  const on = new Set(
    (process.env.FLAGS || '').split(',').map((s) => s.trim()).filter(Boolean)
  );
  return { hasFeature: (name) => on.has(name) };
}

async function realClient() {
  const envKey = process.env.FLAGSMITH_ENV_KEY;
  if (!envKey) return null;
  let sdk;
  try {
    sdk = require('flagsmith-nodejs');
  } catch {
    return null;
  }
  const flagsmith = new sdk.Flagsmith({ environmentKey: envKey });
  await flagsmith.init();
  return flagsmith;
}

async function main() {
  const flagsmith = (await realClient()) || fakeClient();
  const cart = {
    lines: [
      { type: 'item', price: 100 },
      { type: 'discount', price: -20 },
    ],
  };
  try {
    console.log('checkout:', JSON.stringify(checkoutCart(cart, flagsmith)));
  } catch (err) {
    console.log('checkout FAILED:', err.message);
  }
  console.log('banner:', JSON.stringify(showBanner(flagsmith)));
}

if (require.main === module) {
  main().catch((err) => {
    console.error(err);
    process.exitCode = 1;
  });
}

module.exports = { fakeClient };
