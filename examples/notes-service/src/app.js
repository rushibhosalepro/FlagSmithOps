'use strict';

// Entry point. Works offline: flags come from the FLAGS environment variable.
//   node src/app.js
//   FLAGS="search_v2,legacy_export,pdf_preview" node src/app.js

const { search } = require('./search');
const { exportNotes } = require('./export');
const { preview } = require('./preview');

function fakeClient() {
  const on = new Set((process.env.FLAGS || '').split(',').map((s) => s.trim()).filter(Boolean));
  return { hasFeature: (name) => on.has(name) };
}

const NOTES = [
  { id: 1, text: 'buy milk' },
  { id: 2, text: 'call the plumber about the sink' },
];

function main() {
  const flagsmith = fakeClient();
  for (const query of ['milk', '']) {
    try {
      console.log('search %s:', JSON.stringify(query), JSON.stringify(search(NOTES, query, flagsmith).map((n) => n.id)));
    } catch (err) {
      console.log('search %s FAILED: %s', JSON.stringify(query), err.message);
    }
  }
  console.log('export:', exportNotes(NOTES, flagsmith).split('\n')[0]);
  console.log('preview:', JSON.stringify(preview(NOTES[0], flagsmith)));
}

if (require.main === module) {
  main();
}

module.exports = { fakeClient };