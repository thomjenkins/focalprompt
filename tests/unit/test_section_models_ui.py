"""Execute model selection behavior without making paid provider calls."""
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[2]
JS = (REPO / 'static/js/app.js').read_text()


def test_section_model_routing_and_persistence():
    settings = JS.split('// Section model settings.', 1)[1].split('// End section model settings.', 1)[0]
    payload = JS.split("function selectedModelPayload", 1)[1].split('function updateModelDisplay', 1)[0]
    script = """
const assert = require('node:assert/strict');
let userProvider = 'openai', userModel = 'default-model';
const stored = new Map();
const localStorage = { getItem: k => stored.get(k) || null, setItem: (k,v) => stored.set(k,v) };
""" + '// Section model settings.' + settings + '\nfunction selectedModelPayload' + payload + """
const override = {provider: 'anthropic', model: 'section-model'};
sectionModelOverrides.quality = override;
assert.equal(selectedModelPayload('analysis', 'quality').model, 'section-model');
assert.equal(selectedModelPayload('mut', 'quality').mut_provider, 'anthropic');
assert.equal(selectedModelPayload('analysis', 'output').model, 'default-model');
userModel = 'new-default';
assert.equal(selectedModelPayload('analysis', 'quality').model, 'section-model');
assert.equal(pricingModelPayload('mut', 'output').model, 'new-default');
const snapshot = {...getSectionModel('quality')};
sectionModelOverrides.quality = {provider: 'google', model: 'changed-model'};
assert.equal(selectedModelPayload('mut', snapshot).model, 'section-model');
saveSectionModels();
assert.deepEqual(loadSectionModels(), sectionModelOverrides);
assert.deepEqual(normalizeSectionModels({quality: {model: 42}, invalid: override}), {});
stored.set('focalprompt_section_models', 'broken json');
assert.deepEqual(loadSectionModels(), {});
const document = {querySelectorAll: () => []};
function persistModelSelection(provider, model) { userProvider = provider; userModel = model; }
function updateModelDisplay() {}
function updateCostDisplay() {}
const exported = collectModelSettings();
setAllSectionModels({provider: 'google', model: 'global-reset'});
assert.equal(selectedModelPayload('analysis', 'quality').model, 'global-reset');
assert.deepEqual(sectionModelOverrides, {});
restoreModelSettings({model_settings: exported});
assert.equal(selectedModelPayload('analysis', 'quality').model, 'changed-model');
assert.equal(getSectionModel('output').model, 'new-default');
restoreModelSettings({models: {mut: {provider: 'openai', model: 'legacy-mut'}, analysis: {provider: 'openai', model: 'legacy-analysis'}}});
assert.equal(getSectionModel('quality').model, 'legacy-mut');
assert.deepEqual(sectionModelOverrides, {});
userModel = 'new-default';
delete sectionModelOverrides.quality;
assert.equal(selectedModelPayload('analysis', 'quality').model, 'new-default');
"""
    subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)


def test_every_model_call_has_an_explicit_section():
    # Each selectable section must be connected to request routing.
    html = (REPO / 'templates/index.html').read_text()
    import re
    sections = re.findall(r'data-model-section="([^"]+)"', html)
    assert len(sections) == 15
    for section in sections:
        assert re.search(r"[,(] ?'(?:mut|analysis)', '" + section + r"'\)", JS) or section in ('ablation', 'quality')
    assert "getSectionModel('quality')" in JS
    assert "judge.id === 'self' ? 'mut' : 'analysis', judge)" in JS
    assert "'mut', modelSelection" in JS
    assert "const modelSelection = { ...getSectionModel(section) };" in JS
    assert 'model_settings: collectModelSettings()' in JS
    assert 'normalizeSectionModels(data.model_settings?.sections)' in JS
