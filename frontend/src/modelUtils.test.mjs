import test from 'node:test';
import assert from 'node:assert/strict';

import {
  abbreviateModelName,
  formatCurationCost,
  formatCurationList,
  formatCurationText,
  resolveActiveCouncil,
  resolveModelLabel,
  sameModelSet,
} from './modelUtils.js';

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

test('abbreviateModelName produces compact mobile labels', () => {
  const modelMap = new Map([
    ['openai/gpt-4.1', { name: 'OpenAI: GPT-4.1' }],
    ['google/gemini-2.5-pro', { name: 'Google: Gemini 2.5 Pro' }],
    ['anthropic/claude-sonnet-4.6', { name: 'Anthropic: Claude Sonnet 4.6' }],
    ['x-ai/grok-4', { name: 'xAI: Grok 4' }],
    ['deepseek/deepseek-chat', { name: 'DeepSeek: DeepSeek Chat' }],
  ]);

  assert.equal(abbreviateModelName('openai/gpt-4.1', modelMap), 'GPT-4.1');
  assert.equal(abbreviateModelName('google/gemini-2.5-pro', modelMap), 'Gemini 2.5');
  assert.equal(abbreviateModelName('anthropic/claude-sonnet-4.6', modelMap), 'Sonnet 4.6');
  assert.equal(abbreviateModelName('x-ai/grok-4', modelMap), 'Grok 4');
  assert.equal(abbreviateModelName('deepseek/deepseek-chat', modelMap), 'DeepSeek');
  assert.equal(abbreviateModelName('deepseek/deepseek-v4-pro', modelMap), 'DeepSeek 4');
  assert.equal(abbreviateModelName('z-ai/glm-5.2', modelMap), 'GLM 5.2');
});

test('resolveModelLabel matches abbreviated labels used in tabs and headers', () => {
  const modelMap = new Map([
    ['deepseek/deepseek-v4-pro', { name: 'DeepSeek: DeepSeek V4 Pro' }],
    ['openai/gpt-5.4', { name: 'OpenAI: GPT-5.4' }],
  ]);

  assert.equal(resolveModelLabel('deepseek/deepseek-v4-pro', modelMap), 'DeepSeek 4');
  assert.equal(resolveModelLabel('openai/gpt-5.4', modelMap), 'GPT-5.4');
});

test('curation display helpers tolerate structured model output', () => {
  assert.equal(
    formatCurationText({ summary: 'Use the updated frontier mix.' }),
    '{"summary":"Use the updated frontier mix."}',
  );
  assert.deepEqual(
    formatCurationList(['Watch cost.', { issue: 'Catalog may change.' }]),
    ['Watch cost.', '{"issue":"Catalog may change."}'],
  );
  assert.equal(formatCurationCost('0.123456'), '$0.1235');
  assert.equal(formatCurationCost('not-a-number'), null);
});
