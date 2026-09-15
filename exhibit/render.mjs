import { chromium } from "playwright";
const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
for (const [src, out] of [["exhibit.html", "D6-Empty-Tree-Basins-Exhibit.pdf"],
                          ["appendix.html", "D6-Empty-Tree-Basins-Appendix.pdf"]]) {
  const p = await b.newPage();
  const errs = [];
  p.on("pageerror", (e) => errs.push(e.message));
  p.on("requestfailed", (r) => errs.push("missing: " + r.url().split("/").pop()));
  await p.goto(`file:///tmp/claude-0/-home-user-fairtrees/6033c420-3be7-5d5a-929d-e2a8b1fd6fea/scratchpad/${src}`,
               { waitUntil: "networkidle", timeout: 120000 });
  // Make sure every photograph has actually decoded before printing.
  const imgs = await p.evaluate(async () => {
    const list = [...document.images];
    await Promise.all(list.map((i) => i.complete ? null : new Promise((r) => { i.onload = i.onerror = r; })));
    return { total: list.length, broken: list.filter((i) => !i.naturalWidth).length };
  });
  await p.pdf({ path: out, format: "Letter", printBackground: true,
                margin: { top: "0.6in", bottom: "0.75in", left: "0.6in", right: "0.6in" },
                displayHeaderFooter: true,
                headerTemplate: "<div></div>",
                footerTemplate: `<div style="width:100%;font-size:7pt;color:#888;font-family:Helvetica,Arial,sans-serif;padding:0 0.6in;display:flex;justify-content:space-between;">
                   <span>Empty Street-Tree Basins — Supervisor District 6</span>
                   <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>` });
  console.log(`${out}: images=${imgs.total} broken=${imgs.broken} errors=${errs.length ? errs.slice(0,3) : "none"}`);
  await p.close();
}
await b.close();
