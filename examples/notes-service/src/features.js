'use strict';

// A small helper around the SDK. Code search cannot see which flag a call
// to featureOn() reads, because the name is passed in as a variable.

function featureOn(flagsmith, name) {
  return flagsmith.hasFeature(name);
}

module.exports = { featureOn };