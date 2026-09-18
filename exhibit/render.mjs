import { chromium } from "playwright";
const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const p = await b.newPage();
const errs = [];
p.on("pageerror", (e) => errs.push(e.message));
p.on("requestfailed", (r) => errs.push("missing " + r.url().split("/").pop()));
await p.goto("file:///tmp/claude-0/-home-user-fairtrees/6033c420-3be7-5d5a-929d-e2a8b1fd6fea/scratchpad/exhibit_v2.html",
             { waitUntil: "networkidle", timeout: 120000 });
const imgs = await p.evaluate(async () => {
  const l = [...document.images];
  await Promise.all(l.map(i => i.complete ? null : new Promise(r => { i.onload = i.onerror = r; })));
  return { total: l.length, broken: l.filter(i => !i.naturalWidth).length };
});
await p.pdf({ path: "D6-Empty-Tree-Basins.pdf", format: "Letter", printBackground: true,
  margin: { top: "0.7in", bottom: "0.8in", left: "0.7in", right: "0.7in" },
  displayHeaderFooter: true, headerTemplate: "<div></div>",
  footerTemplate: `<div style="width:100%;font-size:7.5pt;color:#777;font-family:Georgia,serif;padding:0 0.7in;display:flex;justify-content:space-between;">
    <span>Empty Street-Tree Basins — Supervisor District 6</span>
    <span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>` });
console.log(`images=${imgs.total} broken=${imgs.broken} errors=${errs.length ? errs.slice(0,3) : "none"}`);
await b.close();
