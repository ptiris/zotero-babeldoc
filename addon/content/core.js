/* SPDX-License-Identifier: AGPL-3.0-or-later */
var BabelDOCController = class {
  constructor({id, version, rootURI}) {
    Object.assign(this, {id, version, rootURI});
    this.windows = new Map(); this.menuIDs = []; this.dialog = null;
    this.state = {busy:false, phase:"请选择文献或 PDF 附件。", progress:0, jobs:[], outputs:[], error:""};
    this.stopped = false; this.cancelled = false; this.process = null; this.launching = false; this.probing = false;
    this.prefPrefix = "extensions.zotero.babeldoc.";
    this.readerHandler = ({reader, doc, append}) => {
      const button = doc.createElement("button");
      button.className = "babeldoc-reader-button";
      button.textContent = "译"; button.title = "使用 BabelDOC 翻译此 PDF";
      button.style.cssText = "padding:2px 8px;border:0;background:transparent;color:inherit;cursor:pointer;font-weight:600";
      button.addEventListener("click", () => this.open([reader.itemID]));
      append(button);
    };
  }
  getPref(name, fallback="") { return Zotero.Prefs.get(this.prefPrefix + name, true) ?? fallback; }
  setPref(name, value) { Zotero.Prefs.set(this.prefPrefix + name, value, true); }
  async startup() {
    await Zotero.PreferencePanes.register({pluginID:this.id, id:"babeldoc-preferences", label:"BabelDOC",
      src:this.rootURI+"content/preferences.xhtml", scripts:[this.rootURI+"content/preferences.js"]});
    Zotero.Reader.registerEventListener("renderToolbar", this.readerHandler, this.id);
    if (Zotero.MenuManager) {
      for (const target of ["main/library/item", "main/menubar/tools"]) {
        this.menuIDs.push(Zotero.MenuManager.registerMenu({pluginID:this.id, menuID:"babeldoc-"+target.replaceAll("/","-"), target,
          menus:[{menuType:"menuitem", onShowing:(event, context) => {
            context.menuElem.setAttribute("label", "BabelDOC 翻译 PDF…");
          }, onCommand:(event, context) => this.open(target === "main/library/item" ? context.items?.map(i=>i.id) : undefined)}]}));
      }
    }
    for (const win of Zotero.getMainWindows()) this.addWindow(win);
  }
  addWindow(win) {
    if (this.windows.has(win)) return;
    const nodes = [];
    if (!Zotero.MenuManager) {
      for (const popupID of ["zotero-itemmenu", "menu_ToolsPopup"]) {
        const popup = win.document.getElementById(popupID); if (!popup) continue;
        const item = win.document.createXULElement("menuitem");
        item.id = "babeldoc-"+popupID; item.setAttribute("label", "BabelDOC 翻译 PDF…");
        item.addEventListener("command", () => this.open()); popup.appendChild(item); nodes.push(item);
      }
    }
    this.windows.set(win, nodes);
  }
  removeWindow(win) { for (const n of this.windows.get(win)||[]) n.remove(); this.windows.delete(win); }
  open(ids) {
    if (!this.state.busy) {
      this.selectedIDs = ids ?? Zotero.getMainWindow()?.ZoteroPane.getSelectedItems().map(i=>i.id) ?? [];
    }
    if (this.dialog && !this.dialog.closed) { this.dialog.focus(); this.dialog.BabelDOCUI?.refresh(); return; }
    this.dialog = Zotero.getMainWindow().openDialog("chrome://zotero-babeldoc/content/console.xhtml", "babeldoc-console",
      "chrome,centerscreen,resizable,width=740,height=790", {controller:this});
  }
  async getPDFs(ids=this.selectedIDs||[]) {
    const results = [], seen = new Set();
    for (const id of ids) {
      const item = await Zotero.Items.getAsync(id); if (!item || item.deleted) continue;
      let pdfs = [];
      if (item.isPDFAttachment()) pdfs = [item];
      else if (item.isRegularItem()) {
        // A parent translates its best original PDF only. Selecting several PDF attachments translates each.
        const attachments = await Zotero.Items.getAsync(item.getAttachments());
        const original = attachments.filter(a=>a.isPDFAttachment() && !a.getField("title").startsWith("BabelDOC ·"));
        const best = await item.getBestAttachment();
        pdfs = [original.find(a=>a.id===best?.id) || original[0]].filter(Boolean);
      }
      for (const pdf of pdfs) if (!seen.has(pdf.id)) {seen.add(pdf.id); results.push(pdf);}
    }
    return results;
  }
  notify(update={}) {
    Object.assign(this.state, update);
    if (this.dialog && !this.dialog.closed) this.dialog.BabelDOCUI?.renderState();
  }
  async getKey(baseURL) {
    const logins = await Services.logins.findLogins("chrome://zotero-babeldoc", null, "BabelDOC");
    return logins.find(l=>l.username===baseURL)?.password || "";
  }
  async saveKey(baseURL, key, remember) {
    const logins = await Services.logins.findLogins("chrome://zotero-babeldoc", null, "BabelDOC");
    for (const login of logins.filter(l=>l.username===baseURL)) Services.logins.removeLogin(login);
    if (remember && key) {
      const login = Components.classes["@mozilla.org/login-manager/loginInfo;1"].createInstance(Components.interfaces.nsILoginInfo);
      login.init("chrome://zotero-babeldoc", null, "BabelDOC", baseURL, key, "", "");
      if (Services.logins.addLoginAsync) await Services.logins.addLoginAsync(login); else Services.logins.addLogin(login);
    }
  }
  subprocessModule() {
    try { return ChromeUtils.importESModule("resource://gre/modules/Subprocess.sys.mjs").Subprocess; }
    catch (_) { return ChromeUtils.import("resource://gre/modules/Subprocess.jsm").Subprocess; }
  }
  async prepareBridge() {
    const base = PathUtils.join(Zotero.DataDirectory.dir, "babeldoc", this.version);
    await IOUtils.makeDirectory(base, {ignoreExisting:true, permissions:0o700});
    const script = PathUtils.join(base, "runner.py");
    // Read from the XPI as well as an unpacked development extension.
    const source = await Zotero.File.getResourceAsync(this.rootURI+"bridge/runner.py");
    await IOUtils.writeUTF8(script, source, {permissions:0o600});
    return {base, script};
  }
  async callRunner(python, request, onEvent, track=true) {
    if (!PathUtils.isAbsolute(python)) throw new Error("请填写 BabelDOC 环境内 Python 可执行文件的绝对路径。");
    const {script} = await this.prepareBridge();
    const proc = await this.subprocessModule().call({command:python, arguments:["-u",script], stderr:"pipe",
      environment:{PYTHONIOENCODING:"utf-8",PYTHONUTF8:"1"},environmentAppend:true});
    if (track) { this.process = proc; if (this.cancelled || this.stopped) await proc.kill(0); }
    let buffer = "", result = null, failure = null, stderr = "";
    const consume = line => {
      if (!line.trim()) return;
      let event; try { event=JSON.parse(line); } catch (_) { return; }
      if (event.type === "finish" || event.type === "probe") result=event;
      if (event.type === "error") failure=event.message;
      onEvent?.(event);
    };
    const drainError = (async () => { let chunk; while ((chunk=await proc.stderr.readString())) {
      // Never display raw dependency logs: they may contain model request content or credentials.
      stderr += chunk; if (stderr.length > 2000) stderr=stderr.slice(-2000);
    } })().catch(()=>{});
    try {
      await proc.stdin.write(JSON.stringify(request)+"\n"); await proc.stdin.close();
      let chunk; while ((chunk=await proc.stdout.readString())) {
        buffer+=chunk; let idx;
        while ((idx=buffer.indexOf("\n"))!==-1) {consume(buffer.slice(0,idx));buffer=buffer.slice(idx+1);}
        if (buffer.length>1048576) throw new Error("翻译引擎输出无效。");
      }
      consume(buffer); const {exitCode}=await proc.wait(); await drainError;
      if (track && (this.cancelled || this.stopped)) throw new Error("任务已取消。");
      if (failure) throw new Error(failure);
      if (exitCode !== 0 || !result) throw new Error(`Python 引擎未正常完成（退出码 ${exitCode}）。请检查 Python 路径及 BabelDOC 0.6.4 安装状态。`);
      return result;
    } catch (error) { await proc.kill(0).catch(()=>{}); throw error; }
    finally { if (track && this.process===proc) this.process=null; }
  }
  async probe(python) {
    if (this.state.busy || this.launching || this.probing) throw new Error("请等待当前任务完成。");
    this.probing=true;
    try { return await this.callRunner(python, {action:"probe"}, null, false); }
    finally { this.probing=false; }
  }
  async translate(settings) {
    if (this.state.busy || this.launching || this.probing || this.stopped) return;
    this.launching=true;
    try { await this.runTranslation(settings); }
    finally { this.launching=false; }
  }
  async runTranslation(settings) {
    const pdfs = await this.getPDFs();
    if (!pdfs.length) throw new Error("请先在文献库选择 PDF 附件或含 PDF 的文献，或从阅读器工具栏打开翻译。");
    if (!settings.api_key) throw new Error("请填写模型服务 API Key。本地无鉴权模型可填写任意非空值。");
    const endpoint = new URL(settings.base_url);
    if (!["http:","https:"].includes(endpoint.protocol) || endpoint.username || endpoint.password) throw new Error("API 地址必须为 HTTP(S) 地址，且不能包含用户名或密码。");
    if (!settings.model.trim()) throw new Error("请填写模型名称。");
    if (!settings.lang_in.trim() || !settings.lang_out.trim()) throw new Error("请填写源语言与目标语言代码。");
    for (const name of ["python","base_url","model","lang_in","lang_out","pages","output_mode","dual_layout","qps","ocr","auto_open"]) this.setPref(name,settings[name]);
    await this.saveKey(settings.base_url, settings.api_key, settings.remember);
    this.cancelled=false;
    this.notify({busy:true, progress:0, phase:"准备翻译…", error:"",jobs:pdfs.map(p=>({id:p.id,title:p.getField("title"),status:"等待"})), outputs:[]});
    let failed = 0;
    try {
      const {base}=await this.prepareBridge();
      for (let index=0;index<pdfs.length;index++) {
        if (this.cancelled || this.stopped) break;
        const source=pdfs[index], job=this.state.jobs[index]; job.status="翻译中";
        let jobDir;
        try {
          const library=Zotero.Libraries.get(source.libraryID);
          if (!library.editable || !library.filesEditable) throw new Error("此文献库没有写入附件的权限。");
          const path=await source.getFilePathAsync();
          if (!path || !await IOUtils.exists(path)) throw new Error("PDF 尚未下载到本地。请先在 Zotero 中打开并下载该附件。");
          jobDir=PathUtils.join(base,"job-"+Zotero.Utilities.randomString(16));
          await IOUtils.makeDirectory(jobDir, {permissions:0o700});
          this.notify({phase:`${index+1}/${pdfs.length} · 正在初始化 BabelDOC（首次会下载字体与模型）`,progress:0});
          const result=await this.callRunner(settings.python, {...settings,action:"translate",input_file:path,output_dir:jobDir}, event=>{
            if (event.type==="progress") this.notify({phase:`${index+1}/${pdfs.length} · ${event.stage}`,progress:event.progress});
          });
          if (this.cancelled || this.stopped) {
            job.status="已取消";
            await IOUtils.remove(jobDir,{recursive:true}); jobDir=null; break;
          }
          this.notify({phase:"保存翻译附件…",progress:100});
          const outputs=[];
          // Persist imported IDs per job so partial import failures remain visible and recoverable.
          for (const output of result.outputs) {
            const outputPath=output.path;
            if (!PathUtils.isAbsolute(outputPath) || PathUtils.parent(outputPath)!==jobDir || !await IOUtils.exists(outputPath)) throw new Error("引擎返回了无效的 PDF 路径。");
            const options={file:outputPath,libraryID:source.libraryID,contentType:"application/pdf",
              title:`BabelDOC · ${settings.lang_out} · ${output.kind==="dual" ? "双语对照" : "译文"}`};
            if (source.parentItemID) options.parentItemID=source.parentItemID;
            else options.collections=source.getCollections();
            const attachment=await Zotero.Attachments.importFromFile(options);
            outputs.push({id:attachment.id,kind:output.kind,title:options.title});
            this.state.outputs.push(outputs[outputs.length-1]); this.notify();
          }
          if (!outputs.length) throw new Error("未生成翻译 PDF。");
          job.status="完成";
          if (settings.auto_open && !this.cancelled && !this.stopped) {
            const preferred=outputs.find(o=>o.kind==="dual") || outputs[0];
            try { await Zotero.Reader.open(preferred.id); }
            catch (_) { this.notify({error:"附件已保存；自动打开失败，请点击下方阅读按钮。"}); }
          }
          await IOUtils.remove(jobDir,{recursive:true}); jobDir=null;
        } catch (error) {
          job.status=this.cancelled ? "已取消" : "失败"; job.error=String(error.message||error); failed++;
          this.notify({error:job.error});
          // Keep successfully generated files on import errors for manual recovery.
          if (jobDir && !this.cancelled) job.recovery=jobDir;
          else if (jobDir) await IOUtils.remove(jobDir,{recursive:true}).catch(()=>{});
        }
        this.notify();
      }
    } catch (error) {
      failed++;
      this.notify({error:String(error.message||error)});
    } finally {
      for (const job of this.state.jobs) if (job.status==="等待") job.status=this.cancelled ? "已取消" : "未开始";
      this.notify({busy:false,phase:this.cancelled ? "任务已取消。" : failed ? `处理结束，${failed} 个任务失败。` : "翻译完成，可在 Zotero 阅读器中打开结果。"});
    }
  }
  async cancel() { this.cancelled=true; this.notify({phase:"正在取消…"}); if (this.process) await this.process.kill(0); }
  async shutdown() {
    this.stopped=true; await this.cancel();
    this.dialog?.close(); this.dialog=null;
    Zotero.Reader.unregisterEventListener("renderToolbar",this.readerHandler);
    for (const reader of Zotero.Reader._readers||[]) {
      reader._iframeWindow?.document.querySelectorAll(".babeldoc-reader-button").forEach(n=>n.remove());
    }
    for (const menu of this.menuIDs) Zotero.MenuManager?.unregisterMenu(menu);
    for (const win of [...this.windows.keys()]) this.removeWindow(win);
  }
};
