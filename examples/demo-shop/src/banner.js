'use strict';

// Fully rolled out promo banner behind the `old_banner` flag.
// Cleanup drill: the sale is over, the flag is on everywhere, and this is
// the only JS reference left. `flag-cleanup` should remove this branch.

function showBanner(flagsmith) {
  if (flagsmith.hasFeature('old_banner')) {
    return 'Winter sale - 20% off!';
  }
  return null;
}

module.exports = { showBanner };
