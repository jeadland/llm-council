import test from 'node:test';
import assert from 'node:assert/strict';

import { resolveActiveCouncil, sameModelSet } from './modelUtils.js';

const presets = [
  {
    id: 'premium',
    name: 'Premium Balanced',
    badge: 'Recommended',
    models: ['model/a', 'model/b'],
    chairman_model: 'model/a',
  },
  {
    id: 'daily',
    name: 'Efficient Daily',
    badge: 'Fast',
    models: ['model/c', 'model/d'],
    chairman_model: 'model/c',
  },
];

test('sameModelSet compares model sets without requiring order', () => {
  assert.equal(sameModelSet(['model/a', 'model/b'], ['model/b', 'model/a']), true);
  assert.equal(sameModelSet(['model/a'], ['model/a', 'model/b']), false);
});

test('active preset id keeps the package name even when selected models need review', () => {
  const active = resolveActiveCouncil({
    active_model_group_id: 'premium',
    council_models: ['model/a'],
    chairman_model: 'model/a',
  }, presets);

  assert.equal(active.name, 'Premium Balanced');
  assert.equal(active.badge, 'Review');
  assert.equal(active.selectionMatchesPreset, false);
});

test('exact resolved preset model set matches when no active id is saved', () => {
  const active = resolveActiveCouncil({
    active_model_group_id: '',
    council_models: ['model/d', 'model/c'],
    chairman_model: 'model/c',
  }, presets);

  assert.equal(active.name, 'Efficient Daily');
  assert.equal(active.badge, 'Fast');
  assert.equal(active.selectionMatchesPreset, true);
});

test('stale selected models do not match a full curated preset by accident', () => {
  const active = resolveActiveCouncil({
    active_model_group_id: '',
    council_models: ['model/a', 'model/missing'],
    chairman_model: 'model/a',
  }, presets);

  assert.equal(active.name, 'Custom Council');
  assert.equal(active.badge, 'Custom');
});
