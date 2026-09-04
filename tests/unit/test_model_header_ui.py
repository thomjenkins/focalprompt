from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def test_index_renders_model_status_inside_lab_nav():
    html = (REPO / 'templates' / 'index.html').read_text(encoding='utf-8')
    nav_start = html.index('class="lab-jump-nav"')
    nav_end = html.index('</nav>', nav_start)
    nav_html = html[nav_start:nav_end]

    assert 'id="model-status-bar"' not in html
    assert 'id="model-status-value"' in html
    assert 'id="model-status-change-btn"' in html
    assert 'class="lab-model-status"' in nav_html
    assert nav_html.index('Quality') < nav_html.index('id="model-status-change-btn"')


def test_app_js_updates_chip_and_lab_nav_model_display():
    js = (REPO / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')

    assert 'function updateModelDisplay()' in js
    assert "document.getElementById('model-chip-label')" in js
    assert "document.getElementById('model-status-value')" in js
    assert "formattedModelSelection('mut')" in js
    assert "formattedModelSelection('analysis')" in js
    assert 'updateModelChipLabel' not in js


def test_settings_ui_configures_mut_and_analysis_models():
    html = (REPO / 'templates' / 'index.html').read_text(encoding='utf-8')

    assert 'Model under test' in html
    assert 'Analysis model' in html
    assert 'id="provider-select"' in html
    assert 'id="analysis-provider-select"' in html
    assert 'id="model-search"' in html
    assert 'id="analysis-model-search"' in html


def test_save_model_selection_refreshes_both_visible_model_roles():
    js = (REPO / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')
    save_block_start = js.index("saveSettingsBtn.addEventListener('click'")
    save_block = js[save_block_start:js.index('updateCostDisplay();', save_block_start)]

    assert "persistModelSelection(mut.provider, mut.model, 'mut');" in save_block
    assert "persistModelSelection(anm.provider, anm.model, 'analysis');" in save_block
    assert save_block.index("persistModelSelection(anm.provider, anm.model, 'analysis');") < save_block.index('updateModelDisplay();')


def test_api_payload_includes_model_roles():
    js = (REPO / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')

    assert "function selectedModelPayload(role = 'analysis')" in js
    assert 'mut_model: mut.model' in js
    assert 'analysis_model: anm.model' in js
    assert "getApiBody({ prompt }, 'mut')" in js


def test_collapsed_settings_hides_the_whole_model_selection_panel():
    js = (REPO / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')

    assert "const settingsSection = document.getElementById('settings-section');" in js
    assert "settingsSection.style.display = expanded ? 'block' : 'none';" in js


def test_css_has_right_aligned_lab_nav_model_status():
    css = (REPO / 'static' / 'css' / 'style.css').read_text(encoding='utf-8')

    assert '.lab-model-status' in css
    assert 'margin-left: auto;' in css
    assert '.model-status-value' in css
