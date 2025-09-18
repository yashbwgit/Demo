#!/usr/bin/env python3
"""
parse_cucumber_reports.py
- Input: single HTML file or directory containing HTML Cucumber reports
- Output:
    - report_summary.json  (aggregated structured output)
    - summary.md            (short human-readable summary)
    - Interactive dashboard (when run with --dashboard flag)
"""
import argparse
import json
import re
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
import sqlite3
from flask import Flask, render_template, jsonify, request
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# Create Flask app
app = Flask(__name__)

# optional fallback parsing
try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

# Database setup
def init_db():
    conn = sqlite3.connect('test_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS test_runs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  total_tests INTEGER,
                  passed INTEGER,
                  failed INTEGER,
                  skipped INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS test_failures
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  run_id INTEGER,
                  test_name TEXT,
                  failure_reason TEXT,
                  file_name TEXT,
                  FOREIGN KEY (run_id) REFERENCES test_runs(id))''')
    conn.commit()
    conn.close()

EXC_RE = re.compile(r'([A-Za-z0-9_.]+(?:Exception|Error|Failure))(?:[:\s-]+)?(.+)?', re.I)

def _extract_reason_from_text(text):
    if not text:
        return None
    m = EXC_RE.search(text)
    if m:
        t = m.group(1)
        msg = m.group(2).strip() if m.group(2) else ""
        return (t + (": " + msg) if msg else t)[:1000]
    # fallback: first non-empty line
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:1000]
    return None

def parse_cucumber_messages_from_html(text):
    """Finds window.CUCUMBER_MESSAGES = [ ... ] in html text and returns parsed list or None"""
    m = re.search(r'window\.CUCUMBER_MESSAGES\s*=\s*(\[[\s\S]*?\])\s*;', text, re.M)
    if not m:
        # some reports may omit trailing semicolon
        m = re.search(r'window\.CUCUMBER_MESSAGES\s*=\s*(\[[\s\S]*\])\s*$', text, re.M)
    if not m:
        return None
    raw = m.group(1)
    try:
        # safe load (these cucumber messages are valid JSON in your samples)
        obj = json.loads(raw)
        return obj
    except Exception:
        # try to be permissive: remove problematic control characters and try again
        raw2 = re.sub(r'\\x[0-9A-Fa-f]{2}', '', raw)
        return json.loads(raw2)

def parse_messages(messages):
    # heuristics: gather mapping from various ids -> scenario name
    pickle_name_by_id = {}       # 'pickle' objects often contain name
    testcase_name_by_id = {}     # direct testCase id -> name
    testcasestarted_to_testcase = {}  # map testCaseStartedId -> testCaseId or pickleId

    failures = []
    counts = Counter()

    # first pass: collect names from messages that declare names
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        # pickles
        if 'pickle' in msg and isinstance(msg['pickle'], dict):
            p = msg['pickle']
            pid = p.get('id')
            name = p.get('name') or p.get('uri') or None
            if pid and name:
                pickle_name_by_id[pid] = name

        # some messages may contain 'testCase' directly
        if 'testCase' in msg and isinstance(msg['testCase'], dict):
            tc = msg['testCase']
            tcid = tc.get('id')
            name = tc.get('name') or tc.get('keyword') or None
            if tcid and name:
                testcase_name_by_id[tcid] = name

        # map started id -> pickle or testCase id
        if 'testCaseStarted' in msg and isinstance(msg['testCaseStarted'], dict):
            tcs = msg['testCaseStarted']
            started_id = tcs.get('id')
            # sometimes they embed testCaseId or pickleId
            tcid = tcs.get('testCaseId') or tcs.get('testCase') or tcs.get('pickleId')
            if started_id and tcid:
                testcasestarted_to_testcase[started_id] = tcid

    # second pass: find step results (status) and extract failures
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        # testStepFinished is a common event
        if 'testStepFinished' in msg and isinstance(msg['testStepFinished'], dict):
            tsf = msg['testStepFinished']
            tcs_id = tsf.get('testCaseStartedId')  # ties to a test-case
            result = tsf.get('testStepResult') or {}
            status = (result.get('status') or '').upper()
            counts[status] += 1
            # if failed, try to get message/exception
            if status == 'FAILED':
                # try direct message
                message = result.get('message') or ''
                exc = result.get('exception') or {}
                reason = None
                if isinstance(exc, dict) and exc.get('type'):
                    reason = exc.get('type') + (": " + exc.get('message') if exc.get('message') else "")
                if not reason:
                    reason = _extract_reason_from_text(message)
                # derive a name for test
                name = "Unknown test"
                if tcs_id:
                    mapped = testcasestarted_to_testcase.get(tcs_id) or tcs_id
                    # check testcase_name_by_id
                    name = testcase_name_by_id.get(mapped) or pickle_name_by_id.get(mapped) or name
                failures.append({
                    'testCaseStartedId': tcs_id,
                    'name': name,
                    'reason': reason or "Unknown failure",
                    'trace': message[:5000]
                })

        # also find high-level testCaseFinished events (sometimes include status)
        elif 'testCaseFinished' in msg and isinstance(msg['testCaseFinished'], dict):
            res = msg['testCaseFinished'].get('testCaseResult') or {}
            status = (res.get('status') or '').upper()
            counts[status] += 0  # no-op; we prefer step-level info

    # totals: fallback if no structured events found
    total = sum(counts.values()) if counts else None

    # aggregate top reasons
    reason_counter = Counter([f['reason'] for f in failures if f.get('reason')])
    top_reasons = [{'reason': r, 'count': c} for r, c in reason_counter.most_common(10)]

    return {
        'total_steps_recorded': total,
        'counts': dict(counts),
        'failures': failures,
        'top_failure_reasons': top_reasons
    }

def fallback_dom_parse(html_path):
    if BeautifulSoup is None:
        raise RuntimeError("BeautifulSoup not installed. Install from requirements.txt")
    with open(html_path, 'r', encoding='utf-8', errors='ignore') as fh:
        soup = BeautifulSoup(fh, 'lxml')

    nodes = soup.find_all(attrs={"data-status": True})
    summary = {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0, 'failures': []}
    fail_counter = Counter()
    for n in nodes:
        status = (n.get('data-status') or '').upper()
        summary['total'] += 1
        if 'PASS' in status:
            summary['passed'] += 1
        elif 'SKIP' in status:
            summary['skipped'] += 1
        elif 'FAIL' in status:
            summary['failed'] += 1
            name = n.get('data-name') or (n.get_text()[:120].strip() or "Unnamed")
            # check for pre/code children for trace
            trace_parts = []
            for p in n.find_all(['pre', 'code', 'div']):
                txt = p.get_text(separator="\n").strip()
                if txt:
                    trace_parts.append(txt)
            trace = "\n".join(trace_parts)[:5000]
            reason = _extract_reason_from_text(trace) or "Unknown failure"
            summary['failures'].append({'name': name, 'reason': reason, 'trace': trace})
            fail_counter[reason] += 1

    summary['top_failure_reasons'] = [{'reason': r, 'count': c} for r, c in fail_counter.most_common(10)]
    return summary

def store_test_run(agg_data):
    """Store test run data in SQLite database"""
    conn = sqlite3.connect('test_history.db')
    c = conn.cursor()
    
    # Insert test run
    c.execute('''INSERT INTO test_runs 
                 (timestamp, total_tests, passed, failed, skipped)
                 VALUES (?, ?, ?, ?, ?)''',
              (datetime.now().isoformat(),
               sum(agg_data['counts'].values()),
               agg_data['counts'].get('PASSED', 0),
               agg_data['counts'].get('FAILED', 0),
               agg_data['counts'].get('SKIPPED', 0)))
    
    run_id = c.lastrowid
    
    # Insert failures
    for failure in agg_data.get('failures', []):
        c.execute('''INSERT INTO test_failures
                     (run_id, test_name, failure_reason, file_name)
                     VALUES (?, ?, ?, ?)''',
                  (run_id,
                   failure.get('name', 'Unknown'),
                   failure.get('reason', 'Unknown'),
                   failure.get('file', 'Unknown')))
    
    conn.commit()
    conn.close()

def aggregate_reports(paths):
    agg_failures = []
    agg_counts = Counter()
    agg_top_reasons = Counter()
    files_parsed = 0
    execution_times = []
    flaky_tests = set()

    for p in paths:
        files_parsed += 1
        text = p.read_text(encoding='utf-8', errors='ignore')
        messages = parse_cucumber_messages_from_html(text)
        if messages:
            res = parse_messages(messages)
            # update counters
            counts = res.get('counts') or {}
            for k, v in counts.items():
                agg_counts[k] += v
            for f in res.get('failures', []):
                agg_failures.append({'file': str(p.name), **f})
                agg_top_reasons[f.get('reason')] += 1
                # Track potential flaky tests (timeouts, race conditions)
                if 'timeout' in f.get('reason', '').lower() or 'race condition' in f.get('reason', '').lower():
                    flaky_tests.add(f.get('name', 'Unknown'))
        else:
            # fallback DOM parsing
            res = fallback_dom_parse(p)
            agg_counts['PASSED'] += res.get('passed', 0)
            agg_counts['FAILED'] += res.get('failed', 0)
            agg_counts['SKIPPED'] += res.get('skipped', 0)
            for f in res.get('failures', []):
                agg_failures.append({'file': str(p.name), **f})
                agg_top_reasons[f.get('reason')] += 1

    aggregated = {
        'files_parsed': files_parsed,
        'counts': dict(agg_counts),
        'total_failures': len(agg_failures),
        'failures': agg_failures,
        'top_failure_reasons': [{'reason': r, 'count': c} for r, c in agg_top_reasons.most_common(10)]
    }
    return aggregated

def write_outputs(agg, json_out_path, md_path='summary.md'):
    with open(json_out_path, 'w', encoding='utf-8') as fh:
        json.dump(agg, fh, indent=2, ensure_ascii=False)

    # markdown summary
    md = []
    md.append("# QA Automated Summary\n")
    md.append(f"- Files parsed: {agg.get('files_parsed')}")
    c = agg.get('counts', {})
    md.append(f"- Passed: {c.get('PASSED',0)}  •  Failed: {c.get('FAILED',0)}  •  Skipped: {c.get('SKIPPED',0)}\n")
    md.append("## Top failure reasons")
    for r in agg.get('top_failure_reasons', [])[:5]:
        md.append(f"- {r['reason']} (count: {r['count']})")
    md.append("\n## Top failing tests (first 10)")
    for f in agg.get('failures', [])[:10]:
        md.append(f"- {f.get('file')}: {f.get('name')} — {f.get('reason')}")
    with open(md_path, 'w', encoding='utf-8') as fh:
        fh.write("\n\n".join(md))

# Flask routes
@app.route('/')
def dashboard():
    conn = sqlite3.connect('test_history.db')
    df = pd.read_sql_query('''
        SELECT timestamp, total_tests, passed, failed, skipped
        FROM test_runs ORDER BY timestamp DESC LIMIT 10
    ''', conn)
    
    # Create visualizations
    trend_fig = px.line(df, x='timestamp', y=['passed', 'failed', 'skipped'],
                        title='Test Results Trend')
    
    # Get latest failure data
    failures_df = pd.read_sql_query('''
        SELECT f.failure_reason, COUNT(*) as count
        FROM test_failures f
        JOIN test_runs r ON f.run_id = r.id
        GROUP BY f.failure_reason
        ORDER BY count DESC LIMIT 5
    ''', conn)
    
    failure_pie = px.pie(failures_df, values='count', names='failure_reason',
                        title='Top Failure Reasons')
    
    conn.close()
    
    return render_template('dashboard.html',
                         trend_plot=trend_fig.to_html(full_html=False),
                         failure_plot=failure_pie.to_html(full_html=False))

@app.route('/api/test-history')
def test_history():
    conn = sqlite3.connect('test_history.db')
    df = pd.read_sql_query('SELECT * FROM test_runs ORDER BY timestamp DESC', conn)
    conn.close()
    return jsonify(df.to_dict('records'))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', required=True, help='HTML file or directory of html reports')
    parser.add_argument('-o', '--output', default='report_summary.json', help='output json file (default: report_summary.json)')
    parser.add_argument('--dashboard', action='store_true', help='Start the dashboard web server')
    args = parser.parse_args()

    if args.dashboard:
        init_db()
        app.run(debug=True)
        return

    p = Path(args.input)
    if p.is_dir():
        files = sorted([x for x in p.glob('**/*.html')])
    elif p.is_file():
        files = [p]
    else:
        print("No input files found.", flush=True)
        raise SystemExit(2)

    agg = aggregate_reports(files)
    write_outputs(agg, args.output, md_path='summary.md')
    store_test_run(agg)  # Store results in database
    print("Wrote:", args.output, "and summary.md")
    print("Totals:", agg.get('counts'))
    print("To view the dashboard, run with --dashboard flag")

if __name__ == '__main__':
    main()
