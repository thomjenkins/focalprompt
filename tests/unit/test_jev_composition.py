"""Composed-prompt provenance must follow saved offsets, never inferred text matches."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def test_recorded_compositions_preserve_every_character_and_source_identity():
    script = r"""
const assert=require('node:assert/strict'),fs=require('node:fs');
const view=require('./static/js/jev_composition.js');
const state=JSON.parse(fs.readFileSync('examples/demos/lisbon/pup4ominiFull.json')).prompt_analysis.jev_experiment.state;
const before=JSON.stringify(state);
for(const arm of ['selected','ordered']) {
 const scenario=state.arms[arm].scenario,preview=state[arm+'_preview'];
 const messages=view.describe(scenario,preview,state.context.foci);
 for(const {message,segments} of messages) {
  assert.equal(segments.map(s=>s.text).join(''),message.content);
  const indices=segments.flatMap(s=>s.foci.map(f=>f.index));
  if(message.analysis_mode==='retain')assert.deepEqual(indices,[]);
  else assert.deepEqual(indices,preview.orders[message.id]);
  for(const segment of segments)for(const f of segment.foci) {
   assert.equal(f.name,state.context.foci[f.index].focus);
   assert.equal(f.color,state.context.foci[f.index].color);
  }
 }
 const html=view.render(scenario,preview,state.context.foci);
 assert.ok(html.includes('Retained chat · unchanged'));
 assert.ok(html.includes('9 foci joined into this message'));
 assert.ok(html.includes('jev-focus-thread'));
 const wrong=structuredClone(preview);wrong.scenario.messages[0].content+='Changed';
 assert.equal(view.render(scenario,wrong,state.context.foci),null);
 const stale=structuredClone(preview);stale.foci[0].spans[0].text_snapshot='Wrong text';
 assert.equal(view.render(scenario,stale,state.context.foci),null);
}
assert.equal(JSON.stringify(state),before);
"""
    subprocess.run(['node', '-e', script], cwd=ROOT, check=True, capture_output=True, text=True)


def test_overlap_repeated_text_and_untrusted_labels_are_rendered_safely():
    script = r"""
const assert=require('node:assert/strict'),view=require('./static/js/jev_composition.js');
const scenario={messages:[{id:'rules',role:'system',analysis_mode:'analyse',content:'A X A <script>'},
 {id:'chat',role:'user',analysis_mode:'retain',content:'A X A'}]};
const sources=[{focus:'<img onerror="bad">',color:'red; bad',colorDark:'" bad'}, {focus:'Shared'}];
const preview={scenario,foci:[
 {focus:sources[0].focus,source_focus_index:0,spans:[{message_id:'rules',char_start:4,char_end:14,text_snapshot:'A <script>'}]},
 {focus:sources[1].focus,source_focus_index:1,spans:[{message_id:'rules',char_start:6,char_end:14,text_snapshot:'<script>'}]}
]};
const messages=view.describe(scenario,preview,sources);
assert.equal(messages[0].segments[0].text,'A X ');
assert.deepEqual(messages[0].segments[0].foci,[]);
assert.deepEqual(messages[0].segments.at(-1).foci.map(f=>f.index),[0,1]);
assert.equal(messages[0].segments.map(s=>s.text).join(''),scenario.messages[0].content);
assert.deepEqual(messages[1].segments[0].foci,[]);
const html=view.render(scenario,preview,sources);
assert.ok(!html.includes('<script>'));assert.ok(!html.includes('<img'));
assert.ok(html.includes('&lt;script&gt;'));assert.ok(html.includes('Shared text'));
assert.ok(!html.includes('red; bad'));assert.ok(html.includes('--jev-focus-bg:#dbeafe'));
preview.foci[0].source_focus_index=99;
assert.equal(view.render(scenario,preview,sources),null);
"""
    subprocess.run(['node', '-e', script], cwd=ROOT, check=True, capture_output=True, text=True)
