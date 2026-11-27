'use strict';

const { test } = require('node:test');
const assert = require('node:assert');
const { search } = require('../src/search');
const { exportNotes } = require('../src/export');
const { preview } = require('../src/preview');

const notes = [{ id: 1, text: 'buy milk' }, { id: 2, text: 'milk and bread' }];
const on = (...names) => ({ hasFeature: (n) => names.includes(n) });
const off = { hasFeature: () => false };

test('search v1 handles an empty query', () => {
  assert.deepStrictEqual(search(notes, '', off).length, 2);
});

test('search v2 ranks results', () => {
  assert.deepStrictEqual(search(notes, 'milk bread', on('search_v2')).map((n) => n.id), [2, 1]);
});

test('search v2 crashes on an empty query (incident drill)', () => {
  assert.throws(() => search(notes, '', on('search_v2')), /empty query/);
});

test('export is CSV when legacy_export is on, JSON when off', () => {
  assert.match(exportNotes(notes, on('legacy_export')), /^id,text/);
  assert.match(exportNotes(notes, off), /^\[/);
});

test('preview is PDF only when pdf_preview is on', () => {
  assert.strictEqual(preview(notes[0], on('pdf_preview')).kind, 'pdf');
  assert.strictEqual(preview(notes[0], off).kind, 'text');
});