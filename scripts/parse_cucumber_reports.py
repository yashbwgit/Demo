#!/usr/bin/env python3
"""
parse_cucumber_reports.py
- Input: single HTML file or directory containing HTML Cucumber reports
- Output:
    - report_summary.json  (aggregated structured output)
    - summary.md            (short human-readable summary)
"""
import argparse
import json
import re
from pathlib import Path
from collections import Counter, defaultdict
 
# optional fallback parsing
try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None
 
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
    # Enhanced data structures to capture more information
    pickle_name_by_id = {}       # 'pickle' objects often contain name
    testcase_name_by_id = {}     # direct testCase id -> name
    testcasestarted_to_testcase = {}  # map testCaseStartedId -> testCaseId or pickleId
    scenario_status = {}         # track scenario-level status
    feature_info = {}           # store feature details
    scenario_info = {}          # store scenario details
    step_info = {}              # store step details
    scenario_steps = defaultdict(list)  # map scenario id to its steps
    scenario_duration = defaultdict(float)  # track scenario durations
    
    failures = []
    counts = Counter()
    
    # first pass: collect feature and scenario information
    for msg in messages:
        if not isinstance(msg, dict):
            continue
            
        # Extract feature information
        if 'gherkinDocument' in msg:
            doc = msg.get('gherkinDocument', {})
            feature = doc.get('feature', {})
            if feature and isinstance(feature, dict):
                fid = feature.get('id')
                if fid:
                    feature_info[fid] = {
                        'name': feature.get('name', 'Unknown Feature'),
                        'description': feature.get('description', ''),
                        'tags': [t.get('name') for t in feature.get('tags', []) if isinstance(t, dict)],
                        'scenarios': []
                    }
        
        # Extract pickle (compiled scenario) information
        if 'pickle' in msg and isinstance(msg['pickle'], dict):
            p = msg['pickle']
            pid = p.get('id')
            name = p.get('name') or p.get('uri') or None
            if pid and name:
                pickle_name_by_id[pid] = name
                # Store detailed scenario information
                scenario_info[pid] = {
                    'name': name,
                    'tags': [t.get('name') for t in p.get('tags', []) if isinstance(t, dict)],
                    'steps': []
                }
                # Link scenario to feature
                if p.get('astNodeIds'):
                    for fid in p.get('astNodeIds', []):
                        if fid in feature_info:
                            feature_info[fid]['scenarios'].append(pid)
 
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
            tcs_id = msg['testCaseFinished'].get('testCaseStartedId')
            status = (res.get('status') or '').upper()
            if tcs_id:
                scenario_status[tcs_id] = status
                counts[status] += 1  # count at scenario level
 
    # Process and organize all collected information
    feature_summary = []
    for fid, feature in feature_info.items():
        feature_scenarios = []
        for sid in feature.get('scenarios', []):
            if sid in scenario_info:
                scenario = scenario_info[sid].copy()
                scenario['steps'] = [step_info[step_id] for step_id in scenario_steps[sid] if step_id in step_info]
                scenario['duration'] = scenario_duration[sid]
                scenario['status'] = scenario_status.get(sid, '')
                feature_scenarios.append(scenario)
        
        feature_summary.append({
            'name': feature.get('name', 'Unknown Feature'),
            'description': feature.get('description', ''),
            'tags': feature.get('tags', []),
            'scenarios': feature_scenarios,
            'total_scenarios': len(feature_scenarios),
            'passed_scenarios': sum(1 for s in feature_scenarios if s['status'] == 'PASSED'),
            'failed_scenarios': sum(1 for s in feature_scenarios if s['status'] == 'FAILED'),
            'skipped_scenarios': sum(1 for s in feature_scenarios if s['status'] == 'SKIPPED'),
            'total_duration': sum(s['duration'] for s in feature_scenarios)
        })

    # Reset counts to use scenario-level status
    counts = Counter(scenario_status.values())
    total = sum(counts.values()) if counts else None
 
    # aggregate top reasons
    reason_counter = Counter([f['reason'] for f in failures if f.get('reason')])
    top_reasons = [{'reason': r, 'count': c} for r, c in reason_counter.most_common(10)]

    # Calculate overall statistics
    total_duration = sum(d for d in scenario_duration.values())
    avg_duration = total_duration / len(scenario_duration) if scenario_duration else 0
 
    return {
        'summary': {
            'total_features': len(feature_summary),
            'total_scenarios': total,
            'counts': dict(counts),
            'total_duration': total_duration,
            'average_scenario_duration': avg_duration
        },
        'features': feature_summary,
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
 
def aggregate_reports(paths):
    agg_failures = []
    agg_counts = Counter()
    agg_top_reasons = Counter()
    files_parsed = 0
 
    for p in paths:
        files_parsed += 1
        text = p.read_text(encoding='utf-8', errors='ignore')
        messages = parse_cucumber_messages_from_html(text)
        if messages:
            res = parse_messages(messages)
            # update counters
            # parse_messages returns counts keyed by step status
            counts = res.get('counts') or {}
            for k, v in counts.items():
                agg_counts[k] += v
            for f in res.get('failures', []):
                agg_failures.append({'file': str(p.name), **f})
                agg_top_reasons[f.get('reason')] += 1
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
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', required=True, help='HTML file or directory of html reports')
    parser.add_argument('-o', '--output', default='report_summary.json', help='output json file (default: report_summary.json)')
    args = parser.parse_args()
 
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
    print("Wrote:", args.output, "and summary.md")
    print("Totals:", agg.get('counts'))
 
if __name__ == '__main__':
    main()