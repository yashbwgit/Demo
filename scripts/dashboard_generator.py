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
#     (re.compile(r'timeout', re.I), "Increase timeouts or add retry logic; investigate slow<header id="dashboard-header"><h1 style="font-size: 28px !important; font-weight: 600 !important;">QA Test Results Dashboard</h1></header>
<div id="dashboard-container">
<div class="dashboard-row">
<div class="dashboard-card" style="flex: 0 0 320px !important;">
    <h3 style="font-size: 20px !important; font-weight: 600 !important; color: #111827 !important; margin-bottom: 20px !important; padding-bottom: 10px !important; border-bottom: 2px solid #e5e7eb !important;">Executive Summary</h3>of dependent services."),
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

def make_html(metrics, analysis):
    total = metrics['total']
    passed = metrics['passed']
    failed = metrics['failed']
    skipped = metrics['skipped']
    pass_rate = (passed/total*100) if total else 0
    system_health = pass_rate

    reasons = [r['reason'] for r in analysis['top_reasons']]
    counts = [r['count'] for r in analysis['top_reasons']]

    example_map = {}
    for f in metrics['failures']:
        if f['name'] not in example_map and f['error']:
            example_map[f['name']] = f['error']

    recs = generate_recommendations(analysis['top_reasons'])

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>QA Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 0; background: #f3f4f6; }}
        .header {{ background: linear-gradient(135deg, #2563eb, #4f46e5); color: white; padding: 24px; text-align: center; }}
        .container {{ max-width: 1200px; margin: 20px auto; padding: 20px; }}
        .row {{ display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 20px; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); flex: 1; min-width: 300px; }}
        .metric {{ display: flex; align-items: center; justify-content: space-between; padding: 10px; margin: 5px 0; background: #f8fafc; border-radius: 6px; }}
        .badge {{ padding: 6px 12px; border-radius: 4px; font-weight: bold; }}
        .success {{ background: #dcfce7; color: #166534; }}
        .error {{ background: #fee2e2; color: #991b1b; }}
        .warning {{ background: #fff7ed; color: #9a3412; }}
        h1 {{ margin: 0; font-size: 24px; }}
        h3 {{ margin: 0 0 15px 0; padding-bottom: 10px; border-bottom: 1px solid #e5e7eb; }}
        pre {{ background: #1e293b; color: #e2e8f0; padding: 15px; border-radius: 6px; overflow: auto; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>QA Test Results Dashboard</h1>
    </div>
    <div class="container">
        <div class="row">
            <div class="card" style="flex: 0 0 300px;">
                <h3>Executive Summary</h3>
                <div class="metric" style="background: #1e40af; color: white;">
                    <div>Total Tests</div>
                    <div style="font-size: 24px;">{total}</div>
                </div>
                <div class="metric">
                    <span class="badge success">✓ Passed</span>
                    <span>{passed}</span>
                </div>
                <div class="metric">
                    <span class="badge error">✗ Failed</span>
                    <span>{failed}</span>
                </div>
                <div class="metric">
                    <span class="badge warning">! Skipped</span>
                    <span>{skipped}</span>
                </div>
                <div class="metric">
                    <div>Pass Rate</div>
                    <div style="color: #059669;">{pass_rate:.1f}%</div>
                </div>
            </div>
            <div class="card">
                <h3>Top Failure Reasons</h3>
                <canvas id="chart" style="width:100%;height:300px;"></canvas>
            </div>
        </div>
        <div class="row">
            <div class="card">
                <h3>Top Failing Tests</h3>"""

    for t in analysis['top_tests'][:20]:
        name = esc(t['name'])
        cnt = t['count']
        trace = esc(example_map.get(t['name'], 'No trace available'))
        html += f"""
                <details style="margin:10px 0;">
                    <summary style="padding:10px;cursor:pointer;background:#f8fafc;border-radius:4px;">
                        {name} — <span style="color:#666;">{cnt} failures</span>
                    </summary>
                    <pre>{trace}</pre>
                </details>"""

    html += """
            </div>
            <div class="card">
                <h3>Recurring Failures</h3>"""

    if analysis['recurring_failures']:
        html += "<ul style='list-style:none;padding:0;margin:0;'>"
        for r in analysis['recurring_failures']:
            html += f"<li style='padding:10px 0;border-bottom:1px solid #e5e7eb;'><b>{esc(r['test'])}</b> — in {r['occurrences']} files</li>"
        html += "</ul>"
    else:
        html += "<div style='color:#666;'>No recurring failures detected.</div>"

    if recs:
        html += "<h3 style='margin-top:20px;'>Suggestions</h3>"
        for rec in recs:
            html += f"""
                <div style="margin:10px 0;padding:15px;background:#f0f9ff;border-radius:4px;border-left:4px solid #2563eb;">
                    <strong>{esc(rec['reason'])}</strong>
                    <div style="margin-top:5px;color:#374151;">{esc(rec['suggestion'])}</div>
                </div>"""

    html += f"""
            </div>
        </div>
    </div>
    <script>
        new Chart(document.getElementById('chart').getContext('2d'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(reasons)},
                datasets: [{{
                    data: {json.dumps(counts)},
                    backgroundColor: '#2563eb'
                }}]
            }},
            options: {{
                indexAxis: 'y',
                plugins: {{ legend: {{ display: false }} }},
                scales: {{ x: {{ beginAtZero: true }} }}
            }}
        }});
    </script>
</body>
</html>"""
    return html
    
    # Generate the complete HTML
    htmlfrag = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>QA Test Results Dashboard</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
            background: #f3f4f6;
            color: #111827;
            line-height: 1.5;
        }}
        .header {{
            background: linear-gradient(135deg, #2563eb, #4f46e5);
            color: white;
            padding: 24px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
        }}
        .container {{
            max-width: 1200px;
            margin: 20px auto;
            padding: 0 20px;
        }}
        .row {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            margin-bottom: 20px;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            padding: 20px;
            flex: 1;
            min-width: 300px;
        }}
        .metric {{
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
        }}
        .badge {{
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 14px;
        }}
        .green {{
            background: #ecfdf5;
            color: #059669;
            border: 1px solid #34d399;
        }}
        .red {{
            background: #fef2f2;
            color: #dc2626;
            border: 1px solid #f87171;
        }}
        .orange {{
            background: #fffbeb;
            color: #d97706;
            border: 1px solid #fbbf24;
        }}
        h3 {{
            margin: 0 0 20px 0;
            font-size: 18px;
            font-weight: 600;
            color: #111827;
            padding-bottom: 10px;
            border-bottom: 1px solid #e5e7eb;
        }}
        pre {{
            background: #1e293b;
            color: #e2e8f0;
            padding: 15px;
            border-radius: 6px;
            overflow: auto;
            max-height: 200px;
            font-size: 13px;
            line-height: 1.5;
        }}
        details {{
            margin-bottom: 10px;
        }}
        summary {{
            cursor: pointer;
            padding: 10px;
            background: #f8fafc;
            border-radius: 4px;
            border: 1px solid #e2e8f0;
        }}
        summary:hover {{
            background: #f1f5f9;
        }}
        .chart-container {{
            min-height: 300px;
            margin-top: 15px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>QA Test Results Dashboard</h1>
    </div>
    <div class="container">
        <div class="row">
            <div class="card" style="flex: 0 0 300px;">
                <h3>Executive Summary</h3>
                <div class="metric" style="background: #1e40af; color: white;">
                    <div>Total Tests</div>
                    <div style="font-size: 24px; font-weight: 600;">{total}</div>
                </div>
                <div class="metric">
                    <span class="badge green">✓ Passed</span>
                    <span style="font-weight: 600;">{passed}</span>
                </div>
                <div class="metric">
                    <span class="badge red">✗ Failed</span>
                    <span style="font-weight: 600;">{failed}</span>
                </div>
                <div class="metric">
                    <span class="badge orange">! Skipped</span>
                    <span style="font-weight: 600;">{skipped}</span>
                </div>
                <div class="metric" style="margin-top: 15px;">
                    <div>Pass Rate</div>
                    <div style="font-weight: 600; color: #059669;">{pass_rate:.1f}%</div>
                </div>
            </div>
            <div class="card" style="flex: 1;">
                <h3>Top Failure Reasons</h3>
                <div class="chart-container">
                    <canvas id="reasonsChart"></canvas>
                </div>
            </div>
        </div>
        
        <div class="row">
            <div class="card">
                <h3>Top Failing Tests</h3>"""
    
    # Add top failing tests
    for t in analysis['top_tests'][:20]:
        name = esc(t['name'])
        cnt = t['count']
        trace = esc(example_map.get(t['name'], 'No trace available'))
        htmlfrag += f"""
                <details>
                    <summary>{name} — <span style="color: #666;">{cnt} failures</span></summary>
                    <pre>{trace}</pre>
                </details>"""
    
    # Add recurring failures section
    htmlfrag += """
            </div>
            <div class="card">
                <h3>Recurring Failures</h3>"""
    
    if analysis['recurring_failures']:
        htmlfrag += "<ul style='list-style:none;padding:0;margin:0;'>"
        for r in analysis['recurring_failures']:
            htmlfrag += f"<li style='padding:10px 0;border-bottom:1px solid #e5e7eb;'><strong>{esc(r['test'])}</strong> — failed in {r['occurrences']} files</li>"
        htmlfrag += "</ul>"
    else:
        htmlfrag += "<div style='color:#666;'>No recurring failures detected across parsed files.</div>"
    
    # Add recommendations
    htmlfrag += "<h3 style='margin-top:20px;'>Quick Suggestions</h3>"
    if recs:
        for rec in recs:
            htmlfrag += f"""
                <div style='margin-top:15px;padding:15px;background:#f0f9ff;border-left:4px solid #2563eb;border-radius:4px;'>
                    <strong>{esc(rec['reason'])}</strong>
                    <div style='margin-top:5px;color:#374151;'>{esc(rec['suggestion'])}</div>
                </div>"""
    else:
        htmlfrag += "<div style='color:#666;'>No automated suggestions available.</div>"
    
    # Close the card and container
    htmlfrag += """
            </div>
        </div>
    </div>
    
    <script>
    const ctx = document.getElementById('reasonsChart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: """ + json.dumps(reasons) + """,
            datasets: [{
                data: """ + json.dumps(counts) + """,
                backgroundColor: '#2563eb',
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    }
                },
                y: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
    </script>
</body>
</html>"""
    return htmlfrag

    # Build map: test name -> error
    example_map={}
    for f in metrics['failures']:
        if f['name'] not in example_map and f['error']:
            example_map[f['name']]=f['error']

    recs=generate_recommendations(analysis['top_reasons'])

    htmlfrag = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>QA Test Results Dashboard</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>
    <style>
        /* Base styles */
        body {{
            margin: 0;
            padding: 0;
            font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
            background: #f3f4f6;
            color: #111827;
        }}
        
        /* Header */
        .header {{
            background: linear-gradient(135deg, #2563eb, #4f46e5);
            color: white;
            padding: 24px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }}
        
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
        }}
        
        /* Container */
        .container {{
            max-width: 1200px;
            margin: 20px auto;
            padding: 0 20px;
        }}
        
        /* Cards */
        .row {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            margin-bottom: 20px;
        }}
        
        .card {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            padding: 20px;
            flex: 1;
            min-width: 300px;
        }}
        
        /* Metrics */
        .metric {{
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
        }}
        
        .badge {{
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 14px;
        }}
        
        .green {{
            background: #ecfdf5;
            color: #059669;
            border: 1px solid #34d399;
        }}
        
        .red {{
            background: #fef2f2;
            color: #dc2626;
            border: 1px solid #f87171;
        }}
        
        .orange {{
            background: #fffbeb;
            color: #d97706;
            border: 1px solid #fbbf24;
        }}
        
        /* Text styles */
        h3 {{
            margin: 0 0 20px 0;
            font-size: 18px;
            font-weight: 600;
            color: #111827;
            padding-bottom: 10px;
            border-bottom: 1px solid #e5e7eb;
        }}
        
        /* Code blocks */
        pre {{
            background: #1e293b;
            color: #e2e8f0;
            padding: 15px;
            border-radius: 6px;
            overflow: auto;
            max-height: 200px;
            font-size: 13px;
            line-height: 1.5;
        }}
        
        /* Details/Summary */
        details {{
            margin-bottom: 10px;
        }}
        
        summary {{
            cursor: pointer;
            padding: 10px;
            background: #f8fafc;
            border-radius: 4px;
            border: 1px solid #e2e8f0;
        }}
        
        summary:hover {{
            background: #f1f5f9;
        }}
        
        /* Chart container */
        .chart-container {{
            min-height: 300px;
            margin-top: 15px;
        }}
    </style>
</head>
<style>
/* Reset and Base Styles */
* {{
    margin: 0 !important;
    padding: 0 !important;
    box-sizing: border-box !important;
}}

html, body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    line-height: 1.5 !important;
    background: #f3f4f6 !important;
    color: #111827 !important;
}}

/* Force all text to be readable */
* {{
    text-rendering: optimizeLegibility !important;
    -webkit-font-smoothing: antialiased !important;
}}
/* Layout Structure */
#dashboard-header {{
    background: linear-gradient(135deg, #2563eb, #4f46e5) !important;
    color: white !important;
    padding: 24px 20px !important;
    text-align: center !important;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;
    margin-bottom: 30px !important;
}}

#dashboard-container {{
    max-width: 1200px !important;
    margin: 0 auto !important;
    padding: 0 20px !important;
}}

.dashboard-row {{
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 20px !important;
    margin-bottom: 20px !important;
    width: 100% !important;
}}

/* Card Styles */
.dashboard-card {{
    background: white !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1), 0 1px 3px rgba(0, 0, 0, 0.08) !important;
    padding: 20px !important;
    flex: 1 1 300px !important;
    min-width: 300px !important;
    border: 1px solid #e5e7eb !important;
    transition: transform 0.2s ease-in-out !important;
}}

.dashboard-card:hover {{
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15) !important;
}}
header h1 {{
  margin: 0;
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: -0.025em;
}}
/* Metrics and Statistics */
.dashboard-metric {{
    padding: 16px !important;
    border-radius: 8px !important;
    margin-bottom: 12px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
}}

.metric-label {{
    font-size: 14px !important;
    font-weight: 500 !important;
    color: #4b5563 !important;
}}

.metric-value {{
    font-size: 20px !important;
    font-weight: 600 !important;
}}

.dashboard-badge {{
    display: inline-flex !important;
    align-items: center !important;
    padding: 6px 12px !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
}}

.badge-success {{
    background-color: #ecfdf5 !important;
    color: #059669 !important;
    border: 1px solid #34d399 !important;
}}

.badge-error {{
    background-color: #fef2f2 !important;
    color: #dc2626 !important;
    border: 1px solid #f87171 !important;
}}

.badge-warning {{
    background-color: #fffbeb !important;
    color: #d97706 !important;
    border: 1px solid #fbbf24 !important;
}}
.card:hover {{
  transform: translateY(-2px);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
}}
.metrics-card {{
  display: grid;
  gap: 1rem;
}}
.metric {{
  display: flex;
  align-items: center;
  gap: 0.75rem;
}}
/* Metrics and Badges */
.badge {{
    display: inline-flex !important;
    align-items: center !important;
    padding: 8px 12px !important;
    border-radius: 6px !important;
    font-weight: bold !important;
    font-size: 14px !important;
    margin: 5px 0 !important;
    min-width: 100px !important;
    justify-content: center !important;
}}

.green {{
    background-color: #dcfce7 !important;
    color: var(--green) !important;
    border: 1px solid #86efac !important;
}}

.red {{
    background-color: #fee2e2 !important;
    color: var(--red) !important;
    border: 1px solid #fca5a5 !important;
}}

.orange {{
    background-color: #ffedd5 !important;
    color: var(--yellow) !important;
    border: 1px solid #fdba74 !important;
}}

.metric {{
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    padding: 10px 0 !important;
    border-bottom: 1px solid #e5e7eb !important;
}}
.card h3 {{
  margin: 0 0 1rem;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text);
}}
pre {{
  background: #1e293b;
  color: #e2e8f0;
  padding: 1rem;
  border-radius: 0.5rem;
  overflow: auto;
  max-height: 240px;
  font-size: 0.875rem;
  line-height: 1.7;
}}
/* Headings and Text */
h1 {{
    font-size: 28px !important;
    font-weight: 700 !important;
    margin: 0 !important;
}}

h3 {{
    font-size: 20px !important;
    font-weight: 600 !important;
    color: #111827 !important;
    margin-bottom: 20px !important;
    padding-bottom: 10px !important;
    border-bottom: 2px solid #e5e7eb !important;
}}

/* Details and Summary */
details {{
    margin-bottom: 15px !important;
    background: #f9fafb !important;
    border-radius: 8px !important;
    padding: 10px !important;
}}

details summary {{
    cursor: pointer !important;
    font-weight: 500 !important;
    padding: 10px !important;
    background: white !important;
    border-radius: 6px !important;
    border: 1px solid #e5e7eb !important;
}}

details summary:hover {{
    background: #f3f4f6 !important;
    border-color: #d1d5db !important;
}}

/* Hints and Tips */
.hint {{
    margin-top: 15px !important;
    padding: 15px !important;
    background-color: #eff6ff !important;
    border-left: 4px solid var(--blue) !important;
    border-radius: 6px !important;
}}
.hint b {{
  color: var(--text);
  display: block;
  margin-bottom: 0.25rem;
}}
ul {{
  list-style-type: none;
  padding: 0;
  margin: 0;
}}
li {{
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}}
li:last-child {{
  border-bottom: none;
}}
.chart-container {{
  margin-top: 1rem;
  min-height: 300px;
}}
</style>
</head><body>
<header><h1>QA Test Results Dashboard</h1></header>
<div class="container">
<div class="row">
  <div class="card" style="flex:0 0 320px !important; background: white !important; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;">
    <h3 style="margin-bottom: 20px !important; padding-bottom: 10px !important; border-bottom: 2px solid #e5e7eb !important;">Executive Summary</h3>
    <div style="background: #f8fafc !important; padding: 15px !important; border-radius: 8px !important; margin-bottom: 20px !important;">
      <div style="font-size: 36px !important; font-weight: bold !important; color: #1e40af !important; text-align: center !important;">{total}</div>
      <div style="text-align: center !important; color: #6b7280 !important; font-size: 14px !important;">Total Tests</div>
    </div>
    <div style="display: grid !important; gap: 10px !important;">
      <div class="metric" style="background: #f0fdf4 !important; padding: 15px !important; border-radius: 8px !important;">
        <span class="badge green" style="font-size: 16px !important;">✓ Passed</span>
        <span style="font-size: 20px !important; font-weight: bold !important; color: #059669 !important;">{passed}</span>
      </div>
      <div class="metric" style="background: #fef2f2 !important; padding: 15px !important; border-radius: 8px !important;">
        <span class="badge red" style="font-size: 16px !important;">⨯ Failed</span>
        <span style="font-size: 20px !important; font-weight: bold !important; color: #dc2626 !important;">{failed}</span>
      </div>
      <div class="metric" style="background: #fffbeb !important; padding: 15px !important; border-radius: 8px !important;">
        <span class="badge orange" style="font-size: 16px !important;">! Skipped</span>
        <span style="font-size: 20px !important; font-weight: bold !important; color: #d97706 !important;">{skipped}</span>
      </div>
    </div>
    <div style="margin-top:0.5rem;padding-top:1rem;border-top:1px solid rgba(0,0,0,0.05)">
      <div class="metric">
        <div>Pass Rate</div>
        <div style="margin-left:auto;font-weight:600;color:var(--success)">{pass_rate:.1f}%</div>
      </div>
      <div class="metric">
        <div>Health Score</div>
        <div style="margin-left:auto;font-weight:600;color:var(--primary)">{system_health:.1f}/100</div>
      </div>
    </div>
  </div>
  
  <div class="card">
    <h3>Top Failure Reasons</h3>
    <div class="chart-container">
      <canvas id="reasonsChart"></canvas>
    </div>
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
const ctx = document.getElementById('reasonsChart').getContext('2d');
Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif';
Chart.defaults.font.size = 13;

const gradient = ctx.createLinearGradient(0, 0, 0, 400);
gradient.addColorStop(0, '#3b82f6');
gradient.addColorStop(1, '#60a5fa');

new Chart(ctx, {{
  type: 'bar',
  data: {{
    labels: {json.dumps(reasons)},
    datasets: [{{
      data: {json.dumps(counts)},
      backgroundColor: gradient,
      borderRadius: 6,
      maxBarThickness: 30
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y',
    scales: {{
      x: {{
        beginAtZero: true,
        grid: {{
          color: 'rgba(0, 0, 0, 0.05)',
          drawBorder: false
        }},
        ticks: {{
          font: {{
            family: "'Inter', sans-serif",
            size: 12
          }}
        }}
      }},
      y: {{
        grid: {{
          display: false,
          drawBorder: false
        }},
        ticks: {{
          font: {{
            family: "'Inter', sans-serif",
            size: 12
          }},
          color: '#4b5563'
        }}
      }}
    }},
    plugins: {{
      legend: {{
        display: false
      }},
      tooltip: {{
        backgroundColor: 'rgba(17, 24, 39, 0.95)',
        titleFont: {{
          family: "'Inter', sans-serif",
          size: 13
        }},
        bodyFont: {{
          family: "'Inter', sans-serif",
          size: 12
        }},
        padding: 12,
        cornerRadius: 8,
        displayColors: false
      }}
    }}
  }}
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
