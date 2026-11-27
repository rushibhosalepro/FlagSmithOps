'use strict';

// CSV export replaced the JSON export and has been on for everyone for months.
// Cleanup drill: the flag is obsolete; keep the ON path (CSV).

function exportJson(notes) {
  return JSON.stringify(notes);
}

function exportCsv(notes) {
  return ['id,text', ...notes.map((n) => `${n.id},"${n.text.replace(/"/g, '""')}"`)].join('\n');
}

function exportNotes(notes, flagsmith) {
  if (flagsmith.hasFeature('legacy_export')) {
    return exportCsv(notes);
  }
  return exportJson(notes);
}

module.exports = { exportNotes, exportCsv, exportJson };