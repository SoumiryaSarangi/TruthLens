// Renders app/static/favicon.svg to the PNG files the page links (apple-touch-icon.png, icon-192.png, icon-512.png). favicon.ico is then
// built from icon-512.png with Pillow:  Image.open("app/static/icon-512.png").save("app/static/favicon.ico", sizes=[(16,16),(32,32),(48,48)])
//   node scripts/make_icons.js        (needs Google Chrome; the path below is the Windows default)
// The SVG is the only source: edit it and rerun. The apple-touch icon is full-bleed (iOS rounds it itself). Provenance: authored in this
// repo from the brand mark in index.html (a magnifier with a check); no third-party artwork.
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const CHROME = process.env.CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const OUT = path.join(__dirname, "..", "app", "static");
const svg = fs.readFileSync(path.join(OUT, "favicon.svg"), "utf8");
const bleed = svg.replace(/<rect width="64" height="64" rx="14"/, '<rect width="64" height="64" rx="0"');
const jobs = [["icon-192.png", 192, svg], ["icon-512.png", 512, svg], ["apple-touch-icon.png", 180, bleed]];
const port = 9300 + Math.floor(Math.random() * 400);
const chrome = spawn(CHROME, ["--headless=new", "--hide-scrollbars", `--remote-debugging-port=${port}`, "--user-data-dir=" + (process.env.TEMP || "/tmp") + "/icons-" + port, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  let t; for (let i = 0; i < 40; i++) { try { t = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); if (t.length) break; } catch (e) {} await sleep(250); }
  const ws = new WebSocket(t.find((x) => x.type === "page").webSocketDebuggerUrl); await new Promise((r) => (ws.onopen = r));
  let id = 0; const pend = {};
  ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pend[d.id]) { pend[d.id](d.result); delete pend[d.id]; } };
  const send = (method, params = {}) => new Promise((r) => { const i = ++id; pend[i] = r; ws.send(JSON.stringify({ id: i, method, params })); });
  for (const [name, size, source] of jobs) {
    await send("Emulation.setDeviceMetricsOverride", { width: size, height: size, deviceScaleFactor: 1, mobile: false });
    await send("Emulation.setDefaultBackgroundColorOverride", { color: { r: 0, g: 0, b: 0, a: 0 } });
    const html = `<!doctype html><meta charset=utf-8><style>html,body{margin:0;background:transparent}svg{display:block;width:${size}px;height:${size}px}</style>${source}`;
    await send("Page.navigate", { url: "data:text/html;charset=utf-8," + encodeURIComponent(html) });
    await sleep(500);
    const shot = await send("Page.captureScreenshot", { format: "png", omitBackground: true });
    fs.writeFileSync(path.join(OUT, name), Buffer.from(shot.data, "base64"));
    console.log("wrote", name, size);
  }
  ws.close(); chrome.kill(); process.exit(0);
})().catch((e) => { console.error(e); chrome.kill(); process.exit(1); });
