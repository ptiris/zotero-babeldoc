var BabelDOCAddon;
var babeldocChrome;
function install() {}
function uninstall() {}
async function startup({ id, version, rootURI }) {
  await Zotero.initializationPromise;
  const aom = Components.classes["@mozilla.org/addons/addon-manager-startup;1"].getService(Components.interfaces.amIAddonManagerStartup);
  babeldocChrome = aom.registerChrome(Services.io.newURI(rootURI + "manifest.json"), [
    ["content", "zotero-babeldoc", rootURI + "content/"]
  ]);
  Services.scriptloader.loadSubScript(rootURI + "content/core.js", this);
  BabelDOCAddon = new BabelDOCController({ id, version, rootURI });
  Zotero.BabelDOC = BabelDOCAddon;
  await BabelDOCAddon.startup();
}
function onMainWindowLoad({ window }) { BabelDOCAddon?.addWindow(window); }
function onMainWindowUnload({ window }) { BabelDOCAddon?.removeWindow(window); }
async function shutdown() {
  if (BabelDOCAddon) await BabelDOCAddon.shutdown();
  delete Zotero.BabelDOC;
  BabelDOCAddon = undefined;
  babeldocChrome?.destruct();
  babeldocChrome = undefined;
}
