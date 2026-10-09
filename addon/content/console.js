/* SPDX-License-Identifier: AGPL-3.0-or-later */
window.BabelDOCUI = {
  defaults:{python:"",base_url:"https://api.openai.com/v1",model:"",lang_in:"en",lang_out:"zh",pages:"",output_mode:"both",dual_layout:"side-by-side",qps:2,ocr:false,auto_open:true},
  fields:["python","base_url","model","lang_in","lang_out","pages","output_mode","dual_layout","qps","ocr","auto_open"],
  async init() {
    this.controller=window.arguments[0].controller;
    for (const field of this.fields) {
      const node=document.getElementById(field), value=this.controller.getPref(field,this.defaults[field]);
      if (node.type==="checkbox") node.checked=Boolean(value); else node.value=value;
    }
    await this.loadKey();
    document.getElementById("base_url").addEventListener("change",()=>this.loadKey().catch(e=>this.error(e)));
    document.getElementById("config").addEventListener("submit",async event=>{
      event.preventDefault();
      try { await this.controller.translate(this.settings()); }
      catch(error) { this.error(error); }
    });
    document.getElementById("cancel").addEventListener("click",()=>this.controller.cancel().catch(e=>this.error(e)));
    document.getElementById("probe").addEventListener("click",async()=>{
      const button=document.getElementById("probe"), status=document.getElementById("probe-status");
      button.disabled=true; status.textContent="正在检查…";
      try {const result=await this.controller.probe(document.getElementById("python").value.trim());
        status.textContent=`环境可用 · BabelDOC ${result.babeldoc} · Python ${result.python}`;
        this.controller.setPref("python",document.getElementById("python").value.trim());
      } catch(error) { status.textContent=error.message; }
      finally { button.disabled=this.controller.state.busy; }
    });
    document.getElementById("refresh-selection").addEventListener("click",()=>{
      this.controller.selectedIDs=this.controller ? this.controllerMainSelection() : [];
      this.refresh().catch(e=>this.error(e));
    });
    await this.refresh();
  },
  controllerMainSelection(){return window.opener.ZoteroPane?.getSelectedItems().map(i=>i.id)||[];},
  async loadKey(){
    const url=document.getElementById("base_url").value.trim();
    const key=await this.controller.getKey(url);
    // Don't overwrite a newly entered key on initialization after the task was reopened.
    document.getElementById("api_key").value=key;
    document.getElementById("remember").checked=Boolean(key);
  },
  settings(){
    const result={};
    for (const field of this.fields) {const node=document.getElementById(field);result[field]=node.type==="checkbox" ? node.checked : node.value.trim();}
    result.qps=Number(result.qps); result.api_key=document.getElementById("api_key").value.trim();
    result.remember=document.getElementById("remember").checked;
    return result;
  },
  error(error){this.controller.notify({error:String(error.message||error)});},
  async refresh(){
    const pdfs=await this.controller.getPDFs();
    const box=document.getElementById("source-list");box.replaceChildren();
    if (!pdfs.length) box.textContent="尚未选择 PDF。请返回文献库选择文献或附件，再点“更新选择”。";
    for (const pdf of pdfs) {const row=document.createElement("div");row.textContent=pdf.getField("title")||pdf.attachmentFilename;box.append(row);}
    this.renderState();
  },
  renderState(){
    const state=this.controller.state;
    document.getElementById("phase").textContent=state.phase;
    document.getElementById("progress").value=state.progress;
    document.getElementById("percent").textContent=state.busy ? `${Math.round(state.progress)}%` : "";
    document.getElementById("error").textContent=state.error;
    document.getElementById("start").disabled=state.busy;
    document.getElementById("cancel").disabled=!state.busy;
    document.getElementById("probe").disabled=state.busy;
    document.getElementById("refresh-selection").disabled=state.busy;
    for (const node of document.querySelectorAll("fieldset")) node.disabled=state.busy;
    const list=document.getElementById("job-list");list.replaceChildren();
    for (const job of state.jobs) {
      const row=document.createElement("li");row.textContent=`${job.title} · ${job.status}`;
      if (job.error) {const small=document.createElement("small");small.textContent=job.error;row.append(small);}
      if (job.recovery) {const small=document.createElement("small");small.textContent="结果保留于："+job.recovery;row.append(small);}
      list.append(row);
    }
    const outputs=document.getElementById("outputs");outputs.replaceChildren();
    for (const output of state.outputs) {
      const button=document.createElement("button");button.type="button";button.textContent="阅读 "+output.title;
      button.addEventListener("click",()=>window.opener.Zotero.Reader.open(output.id).catch(e=>this.error(e)));outputs.append(button);
    }
  }
};
window.addEventListener("DOMContentLoaded",()=>window.BabelDOCUI.init().catch(error=>{
  document.getElementById("error").textContent=String(error.message||error);
}),{once:true});
