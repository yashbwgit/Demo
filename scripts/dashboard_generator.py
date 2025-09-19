# #!/usr/bin/env python3
# """
# dashboard_generator.py
# Usage:
#   python scripts/dashboard_generator.py report_summary.json dashboard.html

# Generates an interactive static dashboard (Chart.js + plain HTML) from the parser's JSON.
# """
# import json
# import sys
# import html
# from pathlib import Path
# from collections import Counter, defaultdict
# import re

# EXC_RE = re.compile(r'([A-Za-z0-9_.]+(?:Exception|Error|Failure|Timeout|AssertionError))', re.I)

# # Simple mapping of hints for common failure reasons
# REMEDY_HINTS = [
#     (re.compile(r'timeout', re.I), "Increase timeouts or add retry logic; investigate slowness of dependent services."),
#     (re.compile(r'nullpointer|null pointer|none type', re.I), "Check input/setup for missing objects; add defensive null checks or fixtures."),
#     (re.compile(r'assert|assertionerror', re.I), "Verify expected values and test data; add clearer assertions and tolerance for timing."),
#     (re.compile(r'no such element|element not found|selector', re.I), "Stabilize selectors, add waits for element visibility, ensure test data/setup."),
#     (re.compile(r'connection refused|connectionreset|refused', re.I), "Check service availability, network issues, and retries/backoff."),
#     (re.compile(r'database|sql|db', re.I), "Verify DB connectivity, migrations and test fixtures; isolate DB tests."),
# ]

# def safe_get(dct, *keys):
#     for k in keys:
#         if isinstance(dct, dict) and k in dct:
#             return dct[k]
#     return None

# def normalize_reason(text):
#     if not text:
#         return "Unknown"
#     # Try to extract exception type
#     m = EXC_RE.search(text)
#     if m:
#         return m.group(1)
#     # fallback: first line trimmed
#     first = text.splitlines()[0].strip()
#     return (first[:120] if first else "Unknown")

# def gather_metrics(data):
#     # Support different shapes: either flat {total, passed, failed} or nested {"summary":{...}}
#     total = safe_get(data, 'total') or safe_get(safe_get(data, 'summary') or {}, 'total') or 0
#     passed = safe_get(data, 'passed') or safe_get(safe_get(data, 'summary') or {}, 'passed') or 0
#     failed = safe_get(data, 'failed') or safe_get(safe_get(data, 'summary') or {}, 'failed') or 0
#     skipped = safe_get(data, 'skipped') or safe_get(safe_get(data, 'summary') or {}, 'skipped') or 0

#     # If totals missing, try to infer from counts dict
#     if not total:
#         counts = safe_get(data, 'counts') or {}
#         if counts:
#             total = sum(counts.values())
#             passed = counts.get('PASSED', passed) or counts.get('passed', passed)
#             failed = counts.get('FAILED', failed) or counts.get('failed', failed)
#             skipped = counts.get('SKIPPED', skipped) or counts.get('skipped', skipped)

#     # failures list (support different keys: 'failures' or nested 'failures')
#     failures = safe_get(data, 'failures') or safe_get(safe_get(data, 'summary') or {}, 'failures') or safe_get(data, 'failures') or []
#     # Ensure list
#     if failures is None:
#         failures = []

#     # Normalize failure entries to dicts with name,file,error
#     norm_failures = []
#     for f in failures:
#         if not isinstance(f, dict):
#             continue
#         name = f.get('name') or f.get('testCase', {}).get('name') or f.get('test', {}).get('name') or f.get('file') or 'Unnamed Test'
#         # error might be stored with different keys
#         error = f.get('error') or f.get('trace') or f.get('reason') or f.get('message') or ''
#         file = f.get('file') or f.get('filename') or ''
#         norm_failures.append({'name': str(name), 'error': str(error), 'file': str(file)})

#     return {
#         'total': int(total or 0),
#         'passed': int(passed or 0),
#         'failed': int(failed or 0),
#         'skipped': int(skipped or 0),
#         'failures': norm_failures
#     }

# def analyze_failures(failures):
#     reason_counter = Counter()
#     test_counter = Counter()
#     test_files = defaultdict(set)  # test -> set(files)
#     reason_examples = defaultdict(list)

#     for f in failures:
#         name = f.get('name') or 'Unnamed Test'
#         err = f.get('error') or ''
#         file = f.get('file') or ''

#         normalized = normalize_reason(err)
#         reason_counter[normalized] += 1
#         test_counter[name] += 1
#         if file:
#             test_files[name].add(file)
#         # keep one example trace per reason (first)
#         if len(reason_examples[normalized]) < 3:
#             reason_examples[normalized].append(err.strip())

#     top_reasons = reason_counter.most_common(10)
#     top_tests = test_counter.most_common(20)

#     recurring = []
#     for test, files in test_files.items():
#         if len(files) > 1:
#             recurring.append({'test': test, 'occurrences': len(files), 'files': list(files)})

#     return {
#         'top_reasons': [{'reason': r, 'count': c, 'examples': reason_examples[r][:2]} for r, c in top_reasons],
#         'top_tests': [{'name': n, 'count': c} for n, c in top_tests],
#         'recurring_failures': recurring
#     }

# def generate_recommendations(top_reasons):
#     recs = []
#     seen = set()
#     for item in top_reasons:
#         reason = item.get('reason','')
#         for pattern, hint in REMEDY_HINTS:
#             if pattern.search(reason):
#                 if reason not in seen:
#                     recs.append({'reason': reason, 'suggestion': hint})
#                     seen.add(reason)
#     if not recs and top_reasons:
#         # fallback generic suggestion
#         recs.append({'reason': top_reasons[0]['reason'], 'suggestion': "Inspect top failure traces and prioritize tests by business impact."})
#     return recs

# def make_html(metrics, analysis):
#     total = metrics['total']
#     passed = metrics['passed']
#     failed = metrics['failed']
#     skipped = metrics['skipped']
#     pass_rate = (passed / total * 100) if total else 0.0
#     # System health: base on pass_rate (you can expand this formula)
#     system_health = pass_rate

#     # Prepare JS data for chart
#     reasons = [r['reason'] for r in analysis['top_reasons']]
#     reason_counts = [r['count'] for r in analysis['top_reasons']]

#     # Escape function for safe HTML
#     def esc(s): return html.escape(str(s))

#     html_frag = f"""<!doctype html>
# <html lang="en">
# <head>
# <meta charset="utf-8">
# <title>QA Dashboard</title>
# <meta name="viewport" content="width=device-width,initial-scale=1">
# <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
# <style>
#   body{{font-family:Inter, Arial, Helvetica, sans-serif; margin:18px; background:#f7f9fb; color:#222}}
#   .row{{display:flex; gap:16px; flex-wrap:wrap}}
#   .card{{background:#fff; padding:14px; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,0.06); flex:1 1 320px}}
#   h1{{margin:0 0 8px 0}}
#   .muted{{color:#666;font-size:0.9em}}
#   ul{ ' { list-style:none; padding:0; margin:0 } ' }
#   li{ ' { margin-bottom:8px } '}
#   .badge{{display:inline-block;padding:6px 10px;border-radius:999px;font-weight:600}}
#   .green{{background:#e6f4ea;color:#086b19}}
#   .red{{background:#ffecec;color:#7a1212}}
#   .orange{{background:#fff4e6;color:#8a4b00}}
#   .small{{font-size:0.9em;color:#444}}
#   details summary{{cursor:pointer;font-weight:600}}
#   pre{{background:#0f1724;color:#e6eef8;padding:10px;border-radius:6px;overflow:auto;max-height:220px}}
#   .hint{ ' { margin-top:6px;padding:10px;border-left:4px solid #ddd;background:#fcfcfd } '}
# </style>
# </head>
# <body>
# <h1>QA Dashboard</h1>
# <div class="muted">One-page summary generated from parser output</div>

# <div class="row" style="margin-top:16px">
#   <div class="card" style="flex: 0 0 320px;">
#     <h3>Executive</h3>
#     <div>Total tests: <strong>{total}</strong></div>
#     <div>Passed: <span class="badge green">✅ {passed}</span></div>
#     <div>Failed: <span class="badge red">❌ {failed}</span></div>
#     <div>Skipped: <span class="badge orange">⚠ {skipped}</span></div>
#     <div style="margin-top:8px">Pass rate: <strong>{pass_rate:.1f}%</strong></div>
#     <div style="margin-top:6px">System Health Score: <strong>{system_health:.1f}</strong>/100</div>
#   </div>

#   <div class="card" style="flex:1 1 600px;">
#     <h3>Top failure reasons</h3>
#     <canvas id="reasonsChart" width="600" height="240"></canvas>
#     <div class="muted small">Top reasons (by count)</div>
#   </div>
# </div>

# <div class="row" style="margin-top:14px;">
#   <div class="card">
#     <h3>Top failing tests</h3>
#     <div class="muted small">Click test to view sample trace</div>
#     <ul>
# """
#     # top tests with sample toggles (we pull examples from failures if available)
#     # We'll embed example traces by scanning metrics['failures']
#     # Build a map: test name -> first example error
#     example_map = {}
#     for f in metrics['failures']:
#         nm = f.get('name') or 'Unnamed'
#         if nm not in example_map and f.get('error'):
#             example_map[nm] = f.get('error')

#     for t in analysis['top_tests'][:20]:
#         name = esc(t['name'])
#         cnt = t['count']
#         example = html.escape(example_map.get(t['name'],'No trace available'))
#         html_frag += f"""      <li>
#         <details>
#           <summary>{name} — <span class="muted small">{cnt} failures</span></summary>
#           <pre>{example}</pre>
#         </details>
#       </li>"""

#     html_frag += """
#     </ul>
#   </div>

#   <div class="card" style="min-width:300px;">
#     <h3>Recurring failures</h3>
# """
#     if analysis['recurring_failures']:
#         html_frag += "<ul>"
#         for r in analysis['recurring_failures']:
#             html_frag += f"<li><strong>{esc(r['test'])}</strong> — failed in {r['occurrences']} files</li>"
#         html_frag += "</ul>"
#     else:
#         html_frag += "<div class='muted small'>No recurring failures detected across parsed files.</div>"

#     # Recommendations
#     recs = generate_recommendations(analysis['top_reasons'])
#     html_frag += "<hr><h3>Quick suggested actions</h3>"
#     if recs:
#         for rec in recs:
#             html_frag += f"<div class='hint'><strong>{esc(rec['reason'])}</strong><div>{esc(rec['suggestion'])}</div></div>"
#     else:
#         html_frag += "<div class='muted small'>No automated suggestions available; inspect traces for root cause.</div>"

#     # Close right column
#     html_frag += """
#   </div>
# </div>

# <script>
# const reasons = """ + json.dumps(reasons) + """;
# const counts = """ + json.dumps(reason_counts) + """;

# const ctx = document.getElementById('reasonsChart').getContext('2d');
# new Chart(ctx, {
#     type: 'bar',
#     data: {
#         labels: reasons,
#         datasets: [{
#             label: 'Failure count',
#             data: counts,
#             backgroundColor: 'rgba(191, 37, 37, 0.85)',
#             borderRadius: 4
#         }]
#     },
#     options: {
#         indexAxis: 'y',
#         scales: {
#             x: { beginAtZero: true }
#         },
#         plugins: { legend: { display: false } }
#     }
# });
# </script>

# </body>
# </html>
# """
#     return html_frag

# def main():
#     if len(sys.argv) < 3:
#         print("Usage: dashboard_generator.py input_json output_html")
#         print("Example: python scripts/dashboard_generator.py report_summary.json dashboard.html")
#         sys.exit(1)

#     in_file = Path(sys.argv[1])
#     out_file = Path(sys.argv[2])

#     if not in_file.exists():
#         print("Input JSON not found:", in_file)
#         sys.exit(2)

#     data = json.loads(in_file.read_text(encoding='utf-8'))
#     metrics = gather_metrics(data)
#     analysis = analyze_failures(metrics['failures'])
#     html = make_html(metrics, analysis)
#     out_file.write_text(html, encoding='utf-8')
#     print("Wrote dashboard:", out_file)

# if __name__ == '__main__':
#     main()


#!/usr/bin/env python3
"""
dashboard_generator.py
Usage:
  python scripts/dashboard_generator.py report_summary.json results/dashboard.html

Generates an interactive static dashboard (Chart.js + styled HTML) from the parser's JSON.
"""
import json, sys, html, re
from pathlib import Path
from collections import Counter, defaultdict

EXC_RE = re.compile(r'([A-Za-z0-9_.]+(?:Exception|Error|Failure|Timeout|AssertionError))', re.I)

REMEDY_HINTS = [
    (re.compile(r'timeout', re.I), "Increase timeouts or add retry logic; investigate slowness of dependent services."),
    (re.compile(r'nullpointer|null pointer|none type', re.I), "Check input/setup for missing objects; add defensive null checks or fixtures."),
    (re.compile(r'assert|assertionerror', re.I), "Verify expected values and test data; add clearer assertions and tolerance for timing."),
    (re.compile(r'no such element|element not found|selector', re.I), "Stabilize selectors, add waits for element visibility, ensure test data/setup."),
    (re.compile(r'connection refused|connectionreset|refused', re.I), "Check service availability, network issues, and retries/backoff."),
    (re.compile(r'database|sql|db', re.I), "Verify DB connectivity, migrations and test fixtures; isolate DB tests."),
]

def esc(s): return html.escape(str(s))

def normalize_reason(text):
    if not text: return "Unknown"
    m = EXC_RE.search(text)
    if m: return m.group(1)
    first = text.splitlines()[0].strip()
    return first[:120] if first else "Unknown"

def gather_metrics(data):
    total = data.get('total') or 0
    passed = data.get('passed') or 0
    failed = data.get('failed') or 0
    skipped = data.get('skipped') or 0
    failures = data.get('failures') or []
    norm_failures=[]
    for f in failures:
        name=f.get('name') or f.get('file') or 'Unnamed Test'
        error=f.get('error') or f.get('trace') or ''
        file=f.get('file','')
        norm_failures.append({'name':name,'error':error,'file':file})
    return {'total':total,'passed':passed,'failed':failed,'skipped':skipped,'failures':norm_failures}

def analyze_failures(failures):
    reason_counter=Counter()
    test_counter=Counter()
    test_files=defaultdict(set)
    reason_examples=defaultdict(list)
    for f in failures:
        name=f['name']; err=f['error']; file=f.get('file','')
        norm=normalize_reason(err)
        reason_counter[norm]+=1
        test_counter[name]+=1
        test_files[name].add(file)
        if len(reason_examples[norm])<3: reason_examples[norm].append(err.strip())
    top_reasons=[{'reason':r,'count':c,'examples':reason_examples[r][:2]} for r,c in reason_counter.most_common(10)]
    top_tests=[{'name':n,'count':c} for n,c in test_counter.most_common(15)]
    recurring=[{'test':t,'occurrences':len(fs)} for t,fs in test_files.items() if len(fs)>1]
    return {'top_reasons':top_reasons,'top_tests':top_tests,'recurring_failures':recurring}

def generate_recommendations(top_reasons):
    recs=[]
    seen=set()
    for r in top_reasons:
        for pat,hint in REMEDY_HINTS:
            if pat.search(r['reason']) and r['reason'] not in seen:
                recs.append({'reason':r['reason'],'suggestion':hint})
                seen.add(r['reason'])
    if not recs and top_reasons:
        recs.append({'reason':top_reasons[0]['reason'],'suggestion':"Inspect top failure traces and prioritize tests by business impact."})
    return recs

def make_html(metrics,analysis):
    total=metrics['total']; passed=metrics['passed']; failed=metrics['failed']; skipped=metrics['skipped']
    pass_rate=(passed/total*100) if total else 0
    system_health=pass_rate

    reasons=[r['reason'] for r in analysis['top_reasons']]
    counts=[r['count'] for r in analysis['top_reasons']]

    # Build map: test name -> error
    example_map={}
    for f in metrics['failures']:
        if f['name'] not in example_map and f['error']:
            example_map[f['name']]=f['error']

    recs=generate_recommendations(analysis['top_reasons'])

    htmlfrag=f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>QA Dashboard</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body{{font-family:'Inter',sans-serif;margin:0;background:#f4f6fb;color:#222}}
header{{background:linear-gradient(90deg,#0072ff,#00c6ff);padding:20px;color:#fff}}
header h1{{margin:0;font-size:1.8em}}
.container{{padding:20px;max-width:1400px;margin:auto}}
.row{{display:flex;flex-wrap:wrap;gap:20px;margin-top:20px}}
.card{{background:#fff;flex:1 1 320px;padding:20px;border-radius:12px;box-shadow:0 3px 6px rgba(0,0,0,0.08);transition:transform .2s}}
.card:hover{{transform:translateY(-3px)}}
.badge{{display:inline-block;padding:6px 10px;border-radius:6px;font-weight:600}}
.green{{background:#e6f4ea;color:#086b19}}
.red{{background:#ffecec;color:#7a1212}}
.orange{{background:#fff4e6;color:#8a4b00}}
pre{{background:#0f1724;color:#e6eef8;padding:10px;border-radius:8px;overflow:auto;max-height:240px}}
details summary{{cursor:pointer;font-weight:600}}
.hint{{margin-top:8px;padding:10px;border-left:4px solid #0072ff;background:#f0f7ff;border-radius:6px}}
ul{{padding-left:18px}}
</style>
</head><body>
<header><h1>QA Test Results Dashboard</h1></header>
<div class="container">
<div class="row">
<div class="card" style="flex:0 0 300px">
<h3>Executive Summary</h3>
Total tests: <b>{total}</b><br>
Passed: <span class="badge green">✅ {passed}</span><br>
Failed: <span class="badge red">❌ {failed}</span><br>
Skipped: <span class="badge orange">⚠ {skipped}</span><br>
Pass rate: <b>{pass_rate:.1f}%</b><br>
System Health Score: <b>{system_health:.1f}</b>/100
</div>
<div class="card">
<h3>Top Failure Reasons</h3>
<canvas id="reasonsChart" height="200"></canvas>
</div>
</div>

<div class="row">
<div class="card">
<h3>Top Failing Tests</h3>
<ul>"""
    for t in analysis['top_tests']:
        nm=esc(t['name']); cnt=t['count']
        trace=esc(example_map.get(t['name'],'No trace available')[:1200])
        htmlfrag+=f"<li><details><summary>{nm} — {cnt} failures</summary><pre>{trace}</pre></details></li>"
    htmlfrag+="</ul></div><div class='card'><h3>Recurring Failures</h3>"
    if analysis['recurring_failures']:
        htmlfrag+="<ul>"+''.join(f"<li><b>{esc(r['test'])}</b> — in {r['occurrences']} files</li>" for r in analysis['recurring_failures'])+"</ul>"
    else:
        htmlfrag+="<div>No recurring failures detected across parsed files.</div>"
    htmlfrag+="<hr><h3>Quick Suggested Actions</h3>"
    if recs:
        for r in recs:
            htmlfrag+=f"<div class='hint'><b>{esc(r['reason'])}</b><div>{esc(r['suggestion'])}</div></div>"
    else:
        htmlfrag+="<div>No automated suggestions available.</div>"
    htmlfrag+="</div></div></div>"

    # Chart.js
    colors=["rgba(191,37,37,0.85)","rgba(255,99,132,0.8)","rgba(255,159,64,0.8)","rgba(255,205,86,0.8)",
            "rgba(75,192,192,0.8)","rgba(54,162,235,0.8)","rgba(153,102,255,0.8)","rgba(201,203,207,0.8)"]
    htmlfrag+=f"""
<script>
const ctx=document.getElementById('reasonsChart').getContext('2d');
new Chart(ctx,{{
 type:'bar',
 data:{{labels:{json.dumps(reasons)},datasets:[{{data:{json.dumps(counts)},backgroundColor:{json.dumps(colors)}.slice(0,{len(reasons)})}}]}},
 options:{{indexAxis:'y',scales:{{x:{{beginAtZero:true}}}},plugins:{{legend:{{display:false}}}}}}
}});
</script>
</body></html>"""
    return htmlfrag

def main():
    if len(sys.argv)<3:
        print("Usage: dashboard_generator.py input_json output_html"); sys.exit(1)
    in_file,out_file=Path(sys.argv[1]),Path(sys.argv[2])
    data=json.loads(in_file.read_text(encoding='utf-8'))
    metrics=gather_metrics(data)
    analysis=analyze_failures(metrics['failures'])
    out_file.write_text(make_html(metrics,analysis),encoding='utf-8')
    print("Wrote dashboard:",out_file)

if __name__=='__main__':
    main()
