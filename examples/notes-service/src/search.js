'use strict';

// New ranked search, behind a flag. Known bug: it crashes on an empty query.
// Incident drill: users get errors from the search box in production.

function searchV1(notes, query) {
  return notes.filter((note) => note.text.includes(query));
}

function searchV2(notes, query) {
  const terms = query.trim().split(/\s+/).filter(Boolean);
  if (terms.length === 0) {
    throw new Error('search v2 cannot handle an empty query');
  }
  return notes
    .map((note) => ({ note, score: terms.filter((t) => note.text.includes(t)).length }))
    .filter((hit) => hit.score > 0)
    .sort((a, b) => b.score - a.score)
    .map((hit) => hit.note);
}

function search(notes, query, flagsmith) {
  if (flagsmith.hasFeature('search_v2')) {
    return searchV2(notes, query);
  }
  return searchV1(notes, query);
}

module.exports = { search, searchV1, searchV2 };