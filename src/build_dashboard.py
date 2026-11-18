"""Self-contained interactive dashboard (one HTML file, Plotly embedded, works offline):
dashboard/reporting_dashboard.html

Tabs: Volume & funnel · Timeliness & backlog · Quality · CAP & readiness. Desk selector (France / Benelux).
Every chart carries a PUBLIC DATA or SIMULATED tag. Numbers come from data/processed (src/run_sql.py, src/findings.py).
    python src/build_dashboard.py
"""
import json
from pathlib import Path

import pandas as pd
from plotly.offline import get_plotlyjs

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "dashboard" / "reporting_dashboard.html"


def rec(name, cols=None):
    d = pd.read_parquet(PROC / f"{name}.parquet")
    for c in d.columns:
        if pd.api.types.is_datetime64_any_dtype(d[c]):
            d[c] = d[c].dt.strftime("%Y-%m-%d")
    if cols:
        d = d[cols]
    return json.loads(d.round(4).to_json(orient="records"))


def data():
    f = json.loads((PROC / "findings.json").read_text(encoding="utf-8"))
    gap = []
    for line in (ROOT / "docs" / "GAP_ANALYSIS.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 11 and cells[0].isdigit():
            gap.append({"n": cells[0], "req": cells[1], "action": cells[6], "priority": cells[9], "status": cells[10]})
    return {"f": f, "funnel": rec("sim_monthly_funnel"), "time": rec("sim_timeliness"), "backlog": rec("sim_backlog_age"),
            "quality": rec("sim_quality_monthly"), "cap": rec("sim_cap_status"), "rules": rec("ibm_rule_results"), "gap": gap}


HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reporting desk dashboard</title>
<style>
:root { color-scheme: light; --bg:#F4F4F2; --card:#FCFCFB; --line:#E1E0D9; --ink:#0B0B0B; --muted:#52514E; --accent:#2A78D6; --pub:#E3EEFB; --pubt:#1C5CAB; --sim:#FBE9E0; --simt:#9A3B12; --red:#D03B3B; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { color-scheme: dark; --bg:#141413; --card:#1A1A19; --line:#33322F; --ink:#F0EFEC; --muted:#C3C2B7; --accent:#3987E5; --pub:#1C2E45; --pubt:#9CC3F2; --sim:#40261A; --simt:#F2B89C; --red:#E66767; } }
:root[data-theme="dark"] { color-scheme: dark; --bg:#141413; --card:#1A1A19; --line:#33322F; --ink:#F0EFEC; --muted:#C3C2B7; --accent:#3987E5; --pub:#1C2E45; --pubt:#9CC3F2; --sim:#40261A; --simt:#F2B89C; --red:#E66767; }
* { box-sizing: border-box; }
body { margin:0; font-family:'Segoe UI', Arial, sans-serif; background:var(--bg); color:var(--ink); }
.wrap { max-width:1280px; margin:0 auto; padding:20px 16px 40px; }
h1 { font-size:22px; margin:0 0 4px; } .sub { color:var(--muted); margin:0 0 14px; font-size:14px; }
.bar { display:flex; gap:10px; flex-wrap:wrap; align-items:center; justify-content:space-between; margin-bottom:12px; }
nav { display:flex; gap:6px; flex-wrap:wrap; }
button, select { border:1px solid var(--line); background:var(--card); color:var(--ink); padding:7px 12px; border-radius:6px; cursor:pointer; font:inherit; font-size:14px; }
nav button.on { background:var(--accent); color:#fff; border-color:var(--accent); }
.tab { display:none; } .tab.on { display:block; }
.grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(min(100%, 520px), 1fr)); gap:12px; }
.kpis { display:grid; grid-template-columns:repeat(auto-fit, minmax(min(100%, 220px), 1fr)); gap:12px; margin-bottom:12px; }
.card { position:relative; background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px 14px; min-width:0; }
.card h2 { font-size:15px; margin:0 0 6px; padding-right:96px; } .card p { font-size:13px; color:var(--muted); margin:4px 0; }
.tag { position:absolute; top:10px; right:10px; font-size:10px; font-weight:700; letter-spacing:.06em; padding:2px 6px; border-radius:4px; }
.pub { background:var(--pub); color:var(--pubt); } .sim { background:var(--sim); color:var(--simt); }
.big { font-size:30px; font-weight:700; margin:2px 0; }
.chart { width:100%; height:330px; }
table { border-collapse:collapse; width:100%; font-size:13px; } th, td { text-align:left; padding:5px 6px; border-bottom:1px solid var(--line); vertical-align:top; }
th { color:var(--muted); font-weight:600; } .warn { color:var(--red); font-weight:600; }
.scroll { overflow-x:auto; }
footer { margin-top:16px; font-size:12px; color:var(--muted); }
</style></head><body><div class="wrap">
<h1>Suspicious-activity reporting desk: volume, timeliness, quality, CAP</h1>
<p class="sub">Desk data are SIMULATED (12 months, two desks, 8 hidden events). Public context: IBM AML rules, Tracfin 2025. Not bunq data.</p>
<div class="bar"><nav id="nav"></nav><label>Desk <select id="desk"><option value="FR">France (treated)</option><option value="BNL">Benelux (control)</option></select></label></div>
<div id="tabs"></div>
<footer>Independent case study based on public data · not affiliated with or endorsed by bunq. KPI definitions: docs/KPI_DEFINITIONS.md.</footer>
</div>
<script>__PLOTLY__</script>
<script>
if (location.hash === "#light" || location.hash === "#dark") document.documentElement.dataset.theme = location.hash.slice(1);
const D = __DATA__;
const TABS = [["vol","Volume & funnel"],["time","Timeliness & backlog"],["qual","Quality"],["cap","CAP & readiness"]];
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const pct = (x, d=0) => (x*100).toFixed(d) + "%";
function layout(extra) { return Object.assign({ margin:{l:48,r:12,t:10,b:40}, paper_bgcolor:"rgba(0,0,0,0)", plot_bgcolor:"rgba(0,0,0,0)",
  font:{family:"Segoe UI, Arial", color:css("--muted"), size:12}, xaxis:{gridcolor:css("--line")}, yaxis:{gridcolor:css("--line"), rangemode:"tozero"},
  legend:{orientation:"h", y:-0.18}, hovermode:"x unified" }, extra || {}); }
const card = (id, title, tag, note) => `<div class="card"><span class="tag ${tag=="PUBLIC DATA"?"pub":"sim"}">${tag}</span><h2>${title}</h2><div id="${id}" class="chart"></div>${note?`<p>${note}</p>`:""}</div>`;
const kpi = (label, val, txt, tag) => `<div class="card"><span class="tag ${tag=="PUBLIC DATA"?"pub":"sim"}">${tag}</span><p>${label}</p><div class="big">${val}</div><p>${txt}</p></div>`;
const f = D.f;
document.getElementById("nav").innerHTML = TABS.map(([k,l],i)=>`<button data-t="${k}" class="${i?"":"on"}">${l}</button>`).join("");
document.getElementById("tabs").innerHTML = `
<section class="tab on" id="t-vol"><div class="kpis">
 ${kpi("Tracfin reports 2025", f.tracfin.str_total_2025.toLocaleString("en"), "+"+pct(f.tracfin.str_growth_2025)+" in a year; banks +"+pct(f.tracfin.banks_growth), "PUBLIC DATA")}
 ${kpi("Rule alerts that are false (IBM AML)", pct(f.ibm.false_alerts_share), "precision "+pct(f.ibm.any_precision,1)+", recall "+pct(f.ibm.any_recall), "PUBLIC DATA")}
 ${kpi("France desk reports / year", f.sim.fr_reports_year.toLocaleString("en"), f.sim.fr_alerts_year.toLocaleString("en")+" alerts", "SIMULATED")}
</div><div class="grid">${card("c-alerts","Alerts per month by source","SIMULATED","New monitoring rule from 2 Mar 2026 (France); year-end scam season in December.")}
 ${card("c-funnel","Funnel: alerts, cases, reports","SIMULATED","Reports counted once per report_id.")}
 ${card("c-rules","Simple rules on IBM AML: precision and recall","PUBLIC DATA","Synthetic labelled data (CDLA-Sharing-1.0), account level.")}</div></section>
<section class="tab" id="t-time"><div class="kpis" id="k-time"></div><div class="grid">
 ${card("c-clock","Median days to file: tool field vs recomputed from the alert","SIMULATED","The tool moved its clock start to case opening on 1 Sep 2026: do not credit the drop.")}
 ${card("c-ontime","Reports within 14 days: Paris vs UTC dates","SIMULATED","Internal target, not a legal deadline.")}
 ${card("c-backlog","Triage backlog at month end, by age","SIMULATED","")}</div></section>
<section class="tab" id="t-qual"><div class="kpis" id="k-qual"></div><div class="grid">
 ${card("c-compl","Completeness at draft and at submission","SIMULATED","Schema change 11 May - 14 Jul 2026 (France).")}
 ${card("c-ret","QA return rate and duplicate submission rows","SIMULATED","Retry bug in June-July.")}</div></section>
<section class="tab" id="t-cap"><div class="kpis" id="k-cap"></div><div class="grid">
 <div class="card"><span class="tag sim">SIMULATED</span><h2>CAP items needing action (31 Oct 2026)</h2><div class="scroll" id="cap-table"></div></div>
 <div class="card"><span class="tag pub">PUBLIC DATA</span><h2>Gap analysis (Tracfin + AMLR from 10 July 2027)</h2><div class="scroll" id="gap-table"></div><p>Process column simulated. To be confirmed with Compliance / Legal; not legal advice.</p></div></div></section>`;
document.querySelectorAll("#nav button").forEach(b => b.onclick = () => {
  document.querySelectorAll("#nav button").forEach(x=>x.classList.toggle("on", x===b));
  document.querySelectorAll(".tab").forEach(t=>t.classList.toggle("on", t.id==="t-"+b.dataset.t));
  window.dispatchEvent(new Event("resize")); });
const sel = document.getElementById("desk");
function draw() {
  const d = sel.value, B = css("--accent"), R = css("--red"), G = "#A3A19A", L = "#C9DDF5";
  const fu = D.funnel.filter(r=>r.desk==d), tm = D.time.filter(r=>r.desk==d), bl = D.backlog.filter(r=>r.desk==d), q = D.quality.filter(r=>r.desk==d);
  const x = a => a.map(r=>r.month);
  Plotly.react("c-alerts", [
    {type:"bar", name:"Monitoring rules", x:x(fu), y:fu.map(r=>r.alerts_rule), marker:{color:B}},
    {type:"bar", name:"Internal referrals", x:x(fu), y:fu.map(r=>r.alerts_internal), marker:{color:L}},
    {type:"bar", name:"External requests", x:x(fu), y:fu.map(r=>r.alerts_external), marker:{color:G}}], layout({barmode:"stack"}), {displayModeBar:false, responsive:true});
  Plotly.react("c-funnel", [
    {type:"scatter", mode:"lines+markers", name:"Alerts", x:x(fu), y:fu.map(r=>r.alerts), line:{color:G}},
    {type:"scatter", mode:"lines+markers", name:"Escalated to case", x:x(fu), y:fu.map(r=>r.escalated), line:{color:B}},
    {type:"scatter", mode:"lines+markers", name:"Reports", x:x(fu), y:fu.map(r=>r.reports), line:{color:R}}], layout(), {displayModeBar:false, responsive:true});
  Plotly.react("c-rules", [
    {type:"bar", orientation:"h", name:"Precision", y:D.rules.map(r=>r.rule.split(" (")[0]), x:D.rules.map(r=>r.precision), marker:{color:B}},
    {type:"bar", orientation:"h", name:"Recall", y:D.rules.map(r=>r.rule.split(" (")[0]), x:D.rules.map(r=>r.recall), marker:{color:L}}],
    layout({barmode:"group", margin:{l:150,r:12,t:10,b:40}, xaxis:{tickformat:".0%", gridcolor:css("--line")}, hovermode:"y unified"}), {displayModeBar:false, responsive:true});
  Plotly.react("c-clock", [
    {type:"scatter", mode:"lines+markers", name:"Tool field", x:x(tm), y:tm.map(r=>r.tool_median_days), line:{color:R}},
    {type:"scatter", mode:"lines+markers", name:"Recomputed from the alert", x:x(tm), y:tm.map(r=>r.true_median_days), line:{color:B, width:3}}],
    layout({shapes:[{type:"line", x0:"2026-09-01", x1:"2026-09-01", yref:"paper", y0:0, y1:1, line:{color:R, dash:"dash"}}]}), {displayModeBar:false, responsive:true});
  Plotly.react("c-ontime", [
    {type:"scatter", mode:"lines+markers", name:"Paris dates (correct)", x:x(tm), y:tm.map(r=>r.on_time_rate), line:{color:B}},
    {type:"scatter", mode:"lines", name:"UTC dates (overstated)", x:x(tm), y:tm.map(r=>r.on_time_rate_utc_check), line:{color:G, dash:"dash"}}],
    layout({yaxis:{tickformat:".0%", range:[0,1.05], gridcolor:css("--line")}, shapes:[{type:"line", xref:"paper", x0:0, x1:1, y0:0.9, y1:0.9, line:{color:R, dash:"dot"}}]}), {displayModeBar:false, responsive:true});
  Plotly.react("c-backlog", [["age_0_6","0-6 days",L],["age_7_13","7-13",B],["age_14_29","14-29",R],["age_30_plus","30+",css("--ink")]].map(([k,n,c]) =>
    ({type:"bar", name:n, x:bl.map(r=>r.month_end), y:bl.map(r=>r[k]), marker:{color:c}})), layout({barmode:"stack"}), {displayModeBar:false, responsive:true});
  Plotly.react("c-compl", [
    {type:"scatter", mode:"lines+markers", name:"Complete at draft", x:x(q), y:q.map(r=>r.complete_at_draft), line:{color:R}},
    {type:"scatter", mode:"lines+markers", name:"Complete at submission", x:x(q), y:q.map(r=>r.complete_at_submission), line:{color:B}}],
    layout({yaxis:{tickformat:".0%", range:[0.7,1.02], gridcolor:css("--line")}}), {displayModeBar:false, responsive:true});
  Plotly.react("c-ret", [
    {type:"bar", name:"QA return rate", x:x(q), y:q.map(r=>r.qa_return_rate), marker:{color:L}},
    {type:"scatter", mode:"lines+markers", name:"Duplicate rows", x:x(q), y:q.map(r=>r.duplicate_submission_rows), yaxis:"y2", line:{color:R}}],
    layout({yaxis:{tickformat:".0%", gridcolor:css("--line")}, yaxis2:{overlaying:"y", side:"right", rangemode:"tozero", showgrid:false}}), {displayModeBar:false, responsive:true});
  const t = tm[tm.length-1], s = f.sim;
  document.getElementById("k-time").innerHTML = (d=="FR" ? kpi("Tool says (Aug → Sep)", (s.tool_change_pct*100).toFixed(0)+"%", "time to file; recomputed from the alert: "+(s.true_change_pct*100).toFixed(1)+"%", "SIMULATED") : "")
    + kpi("On-time, last month", pct(t.on_time_rate), "UTC check would say "+pct(t.on_time_rate_utc_check), "SIMULATED")
    + kpi("Median days to file, last month", t.true_median_days.toFixed(1), "from the alert; p90 "+t.true_p90_days.toFixed(1), "SIMULATED");
  const qq = q.reduce((a,r)=>({n:a.n+r.reports, d:a.d+r.duplicate_submission_rows}), {n:0,d:0});
  document.getElementById("k-qual").innerHTML = kpi("Reports in 12 months", qq.n.toLocaleString("en"), "distinct report_id", "SIMULATED")
    + kpi("Duplicate submission rows", qq.d, "excluded from every count", "SIMULATED")
    + (d=="FR" ? kpi("Pre-fill effect (DiD)", (f.did.did_pct*100).toFixed(0)+"%", "effort per case, 95% CI "+(f.did.ci_low_pct*100).toFixed(0)+"% to "+(f.did.ci_high_pct*100).toFixed(0)+"%", "SIMULATED") : "");
}
const capAct = D.cap.filter(r=>["overdue","closed without evidence","due within 14 days"].includes(r.cap_state));
document.getElementById("k-cap").innerHTML = kpi("CAP items", f.cap.items, f.cap.on_time+" closed on time with evidence", "SIMULATED")
  + kpi("Overdue", f.cap.overdue, "owner team(s): "+f.cap.overdue_teams.join(", "), "SIMULATED") + kpi("Closed without evidence", f.cap.no_evidence, "counted as not done", "SIMULATED");
document.getElementById("cap-table").innerHTML = "<table><tr><th>CAP</th><th>Item</th><th>Team</th><th>Due</th><th>State</th></tr>" +
  capAct.map(r=>`<tr><td>${r.cap_id}</td><td>${r.item}</td><td>${r.owner_team}</td><td>${r.due_date.slice(0,10)}</td><td class="warn">${r.cap_state}</td></tr>`).join("") + "</table>";
document.getElementById("gap-table").innerHTML = "<table><tr><th>#</th><th>Requirement</th><th>Action</th><th>Priority</th><th>Status</th></tr>" +
  D.gap.map(r=>`<tr><td>${r.n}</td><td>${r.req}</td><td>${r.action}</td><td class="${r.priority.includes("high")?"warn":""}">${r.priority}</td><td>${r.status}</td></tr>`).join("") + "</table>";
sel.onchange = draw; draw();
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
</script></body></html>"""


def main():
    html = HTML.replace("__PLOTLY__", get_plotlyjs()).replace("__DATA__", json.dumps(data()))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print("written", OUT.relative_to(ROOT), f"{OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
