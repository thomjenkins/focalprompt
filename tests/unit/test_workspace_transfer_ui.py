"""Separate-tab handoff accepts only its paired window after lab initialization."""
from pathlib import Path
import subprocess


def test_transfer_identity_readiness_failures_and_no_persistent_prompt_storage():
    source = (Path(__file__).resolve().parents[2] / 'static/js/workspace_transfer.js').read_text()
    script = r"""
const assert = require('node:assert/strict'), vm = require('node:vm');
function surface(hash='') {
 const listeners = new Map(), sent=[], timers=new Set();
 const w={location:{href:'https://example.test/lab'+hash,origin:'https://example.test',pathname:'/lab',hash},
  addEventListener:(name,fn)=>{const set=listeners.get(name)||new Set();set.add(fn);listeners.set(name,set);},
  removeEventListener:(name,fn)=>listeners.get(name)?.delete(fn),
  history:{replaceState(...args){w.history.args=args;}}};
 const element={textContent:'',hidden:true,scrollIntoView(){}};
 const scope={window:w,URL,Blob,crypto:{randomUUID:()=> 'token-123'},
  document:{getElementById:()=>element},
  setTimeout:fn=>{timers.add(fn);return fn;},clearTimeout:fn=>timers.delete(fn),
  validateWorkspaceSession:d=>d.focalprompt_workspace?null:'Invalid workspace'};
 return {w,scope,sent,timers,listeners,element,
  emit(name,event){for(const fn of [...(listeners.get(name)||[])])fn(event);},
  start(){vm.runInNewContext(SOURCE,scope);}};
}
const message=(source,type,token='token-123',origin='https://example.test',extra={})=>({source,origin,data:{type:'focalprompt-workspace-'+type,token,...extra}});
(async()=>{
 const p=surface();let closed=false;
 const child={postMessage:(data,origin)=>p.sent.push({data,origin}),close(){closed=true;}};
 p.w.open=()=>child;p.start();
 let finish;const pending=p.w.FocalPromptWorkspaceTransfer.open(()=>new Promise(resolve=>finish=resolve));
 await Promise.resolve();
 p.emit('message',message({},'ready'));
 p.emit('message',message(child,'ready','wrong-token'));
 p.emit('message',message(child,'ready','token-123','https://wrong.test'));
 assert.equal(p.sent.length,0);
 p.emit('message',message(child,'ready'));assert.equal(p.sent.length,0,'wait for composition');
 finish({focalprompt_workspace:true,private_text:'Only send to paired window'});
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(p.sent.length,1);assert.equal(p.sent[0].origin,'https://example.test');
 assert.equal(p.sent[0].data.workspace.private_text,'Only send to paired window');
 p.emit('message',message(child,'loaded'));await pending;
 assert.equal(closed,false);assert.equal(p.timers.size,0);assert.equal(p.listeners.get('message').size,0);
 p.w.open=()=>null;let prepared=false;
 await assert.rejects(p.w.FocalPromptWorkspaceTransfer.open(()=>{prepared=true;}),/browser blocked/);
 assert.equal(prepared,false);
 p.w.open=()=>child;
 await assert.rejects(p.w.FocalPromptWorkspaceTransfer.open(()=>{throw new Error('Composition failed');}),/Composition failed/);
 assert.equal(closed,true);assert.equal(p.listeners.get('message').size,0);

 const c=surface('#analysis=token-123'), restored=[];
 const opener={postMessage:(data,origin)=>c.sent.push({data,origin})};
 c.w.opener=opener;c.w.restoreWorkspaceSession=d=>restored.push(d);c.start();
 assert.equal(c.sent.length,0,'must wait for saved prompt/model initialization');
 c.emit('focalprompt:ready',{});assert.equal(c.sent[0].data.type,'focalprompt-workspace-ready');
 const data={focalprompt_workspace:true};
 c.emit('message',message({},'load','token-123','https://example.test',{workspace:data}));
 c.emit('message',message(opener,'load','bad-token','https://example.test',{workspace:data}));
 c.emit('message',message(opener,'load','token-123','https://wrong.test',{workspace:data}));
 assert.equal(restored.length,0);
 c.emit('message',message(opener,'load','token-123','https://example.test',{workspace:data}));
 assert.equal(restored.length,1);assert.equal(c.w.opener,null);
 assert.equal(c.sent[1].data.type,'focalprompt-workspace-loaded');
 assert.equal(c.w.history.args[2],'/lab#lab-prospective');
 c.emit('message',message(opener,'load','token-123','https://example.test',{workspace:data}));
 assert.equal(restored.length,1,'only one import');
 // No localStorage/sessionStorage API exists in either test surface.
})().catch(e=>{console.error(e);process.exit(1)});
""".replace('SOURCE', repr(source))
    subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)
