'use strict';

const { featureOn } = require('./features');

// PDF preview is still being rolled out (on in Development only). Not obsolete.

function preview(note, flagsmith) {
  if (featureOn(flagsmith, 'pdf_preview')) {
    return { kind: 'pdf', id: note.id };
  }
  return { kind: 'text', id: note.id };
}

module.exports = { preview };