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
    assert 'updateModelChipLabel' not in js


def test_save_model_selection_refreshes_visible_model_display():
    js = (REPO / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')
    save_block_start = js.index("saveSettingsBtn.addEventListener('click'")
    save_block = js[save_block_start:js.index('updateCostDisplay();', save_block_start)]

    assert 'persistModelSelection(sel.provider, sel.model);' in save_block
    assert save_block.index('persistModelSelection(sel.provider, sel.model);') < save_block.index('updateModelDisplay();')


def test_collapsed_settings_hides_the_whole_model_selection_panel():
    js = (REPO / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')

    assert "const settingsSection = document.getElementById('settings-section');" in js
    assert "settingsSection.style.display = expanded ? 'block' : 'none';" in js


def test_css_has_right_aligned_lab_nav_model_status():
    css = (REPO / 'static' / 'css' / 'style.css').read_text(encoding='utf-8')

    assert '.lab-model-status' in css
    assert 'margin-left: auto;' in css
    assert '.model-status-value' in css
