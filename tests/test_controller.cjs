const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const test = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../addon/content/core.js'), 'utf8');
function fixture() {
  const items=new Map(), prefs=new Map(), imported=[], removed=[], opened=[];
  const win={closed:false,ZoteroPane:{getSelectedItems:()=>[]},openDialog:()=>({closed:false,close(){this.closed=true}})};
  const ctx={URL,console,PathUtils:{join:path.join,parent:path.dirname,isAbsolute:path.isAbsolute},
    IOUtils:{exists:async()=>true,makeDirectory:async()=>{},remove:async p=>removed.push(p)},
    Services:{logins:{findLogins:()=>[],removeLogin(){}}},
    Zotero:{DataDirectory:{dir:'/tmp/data'},Items:{getAsync:async ids=>Array.isArray(ids)?ids.map(id=>items.get(id)):items.get(ids)},
      Prefs:{get:(k)=>prefs.get(k),set:(k,v)=>prefs.set(k,v)},getMainWindow:()=>win,
      Libraries:{get:()=>({editable:true,filesEditable:true})},Utilities:{randomString:()=>String(imported.length+1)},
      Attachments:{importFromFile:async options=>{imported.push(options);return {id:100+imported.length}}},
      Reader:{open:async id=>opened.push(id)}}};
  vm.createContext(ctx);vm.runInContext(source+';globalThis.Controller=BabelDOCController;',ctx);
  const controller=new ctx.Controller({id:'test',version:'0.1.0',rootURI:'file:///addon/'});
  controller.prepareBridge=async()=>({base:'/tmp/jobs',script:'/tmp/runner.py'});
  const settings={python:'/python',api_key:'test-key',base_url:'http://localhost:9999/v1',model:'fixture',lang_in:'en',lang_out:'zh',qps:2,pages:'',output_mode:'both',dual_layout:'side-by-side',ocr:false,auto_open:true,remember:false};
  function pdf(id,parentItemID=null){return {id,parentItemID,libraryID:1,isPDFAttachment:()=>true,isRegularItem:()=>false,
    getField:()=>`Source ${id}`,getCollections:()=>[12],getFilePathAsync:async()=>`/tmp/input-${id}.pdf`};}
  function successRunner(){controller.callRunner=async(p,request,onEvent)=>{onEvent?.({type:'progress',stage:'Translating',progress:40});
    return {type:'finish',outputs:[{kind:'mono',path:path.join(request.output_dir,'mono.pdf')},{kind:'dual',path:path.join(request.output_dir,'dual.pdf')}]};};}
  return {controller,ctx,settings,items,prefs,imported,removed,opened,pdf,successRunner};
}
test('selection deduplicates a parent and its explicitly selected original PDF', async()=>{
  const f=fixture();const pdf=f.pdf(2);f.items.set(2,pdf);f.items.set(1,{id:1,isPDFAttachment:()=>false,isRegularItem:()=>true,getAttachments:()=>[2],getBestAttachment:async()=>pdf});
  const result=await f.controller.getPDFs([1,2]);assert.equal(result.length,1);assert.equal(result[0].id,2);
});
test('generated BabelDOC attachments are excluded when translating a parent',async()=>{
  const f=fixture(), original=f.pdf(2), generated=f.pdf(3);generated.getField=()=> 'BabelDOC · zh · 双语对照';
  f.items.set(2,original);f.items.set(3,generated);f.items.set(1,{id:1,isPDFAttachment:()=>false,isRegularItem:()=>true,getAttachments:()=>[3,2],getBestAttachment:async()=>generated});
  assert.equal((await f.controller.getPDFs([1]))[0].id,2);
});
test('both PDFs attach to original parent and dual opens in Zotero Reader',async()=>{
  const f=fixture();f.items.set(2,f.pdf(2,1));f.controller.selectedIDs=[2];f.successRunner();await f.controller.translate(f.settings);
  assert.equal(f.imported.length,2);assert.equal(f.imported[0].parentItemID,1);assert.equal(f.imported[0].collections,undefined);
  assert.equal(f.opened[0],102);assert.equal(f.controller.state.jobs[0].status,'完成');assert.equal(f.controller.state.busy,false);
  assert.equal([...f.prefs.keys()].some(k=>/api_key|remember/.test(k)),false);
});
test('standalone translated PDF retains library and collections',async()=>{
  const f=fixture();f.items.set(2,f.pdf(2));f.controller.selectedIDs=[2];f.successRunner();await f.controller.translate(f.settings);
  assert.equal(f.imported[0].libraryID,1);assert.deepEqual(f.imported[0].collections,[12]);
});
test('read-only library fails before any model invocation',async()=>{
  const f=fixture();f.items.set(2,f.pdf(2));f.controller.selectedIDs=[2];f.ctx.Zotero.Libraries.get=()=>({editable:false,filesEditable:false});
  f.controller.callRunner=async()=>assert.fail('model must not be invoked');await f.controller.translate(f.settings);
  assert.equal(f.imported.length,0);assert.equal(f.controller.state.jobs[0].status,'失败');
});
test('an engine failure does not stop later selected PDFs',async()=>{
  const f=fixture();f.items.set(2,f.pdf(2));f.items.set(3,f.pdf(3));f.controller.selectedIDs=[2,3];let calls=0;
  f.successRunner();const success=f.controller.callRunner;f.controller.callRunner=async(...args)=>{if(++calls===1)throw Error('fixture error');return success(...args)};
  await f.controller.translate(f.settings);assert.equal(f.controller.state.jobs[0].status,'失败');assert.equal(f.controller.state.jobs[1].status,'完成');assert.equal(f.imported.length,2);
});
test('cancelled engine result imports nothing and clears remaining queue',async()=>{
  const f=fixture();f.items.set(2,f.pdf(2));f.items.set(3,f.pdf(3));f.controller.selectedIDs=[2,3];
  f.successRunner();const success=f.controller.callRunner;f.controller.callRunner=async(...args)=>{await f.controller.cancel();return success(...args)};
  await f.controller.translate(f.settings);assert.equal(f.imported.length,0);assert.equal(f.controller.state.jobs[0].status,'已取消');assert.equal(f.controller.state.jobs[1].status,'已取消');assert.equal(f.controller.state.busy,false);
});
test('preparation failure releases busy flag and reports failure',async()=>{
  const f=fixture();f.items.set(2,f.pdf(2));f.controller.selectedIDs=[2];f.controller.prepareBridge=async()=>{throw Error('permission denied')};
  await f.controller.translate(f.settings);assert.equal(f.controller.state.busy,false);assert.match(f.controller.state.error,/permission denied/);
});
test('partial attachment import failure keeps generated files for recovery',async()=>{
  const f=fixture();f.items.set(2,f.pdf(2));f.controller.selectedIDs=[2];f.successRunner();const importer=f.ctx.Zotero.Attachments.importFromFile;
  f.ctx.Zotero.Attachments.importFromFile=async options=>{if(f.imported.length===1)throw Error('second import failed');return importer(options)};
  await f.controller.translate(f.settings);assert.equal(f.controller.state.outputs.length,1);assert.ok(f.controller.state.jobs[0].recovery);assert.equal(f.removed.length,0);
});
test('repeated starts create only one batch while selection resolves',async()=>{
  const f=fixture();f.items.set(2,f.pdf(2));f.controller.selectedIDs=[2];f.successRunner();
  await Promise.all([f.controller.translate(f.settings),f.controller.translate(f.settings)]);assert.equal(f.imported.length,2);
});
test('probe remains usable after a previous cancellation',async()=>{
  const f=fixture();f.controller.cancelled=true;f.controller.callRunner=async(p,r,event,track)=>{assert.equal(track,false);return {type:'probe'}};
  assert.equal((await f.controller.probe('/python')).type,'probe');
});
