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
    """Extract test results from either window.MESSAGES or HTML content"""
    print("Starting file parse...")
    print(f"File length: {len(text)} characters")
    
    # Look for JSON data with more permissive pattern
    json_patterns = [
        r'window\.CUCUMBER_MESSAGES\s*=\s*(\[[\s\S]*?\])\s*[;\n]',
        r'"cucumberJson"\s*:\s*(\[[\s\S]*?\])\s*[,\n}]',
        r'var\s+jsonReport\s*=\s*(\[[\s\S]*?\])\s*[;\n]'
    ]
    
    for pattern in json_patterns:
        print(f"Trying pattern: {pattern}")
        json_match = re.search(pattern, text)
        if json_match:
            try:
                print("Found JSON data, attempting to parse...")
                json_raw = json_match.group(1)
                print(f"Raw JSON length: {len(json_raw)} characters")
                print("First 100 chars:", json_raw[:100])
                json_data = json.loads(json_raw)
                print("Successfully parsed JSON")
                return json_data
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
    
    print("No valid JSON found, trying HTML parsing...")
    
    if BeautifulSoup is None:
        raise RuntimeError("BeautifulSoup not installed. Install from requirements.txt")
    
    soup = BeautifulSoup(text, 'lxml')
    print("BeautifulSoup parsed HTML")
    
    # Search for various possible test result indicators
    results = []
    
    # Common class patterns for cucumber/test reports
    test_class_patterns = [
        'scenario', 'test', 'step', 'feature',
        'passed', 'failed', 'skipped',
        'cucumber', 'report', 'result'
    ]
    
    # Find elements by class patterns
    for pattern in test_class_patterns:
        elements = soup.find_all(class_=re.compile(pattern, re.I))
        print(f"Found {len(elements)} elements with class pattern '{pattern}'")
        for elem in elements:
            # Try to determine status
            text = elem.get_text().lower()
            name = elem.get('name', '') or elem.get('title', '') or text[:120]
            
            # Look for status in various attributes and content
            status = None
            if any(word in text for word in ['passed', 'success']):
                status = 'PASSED'
            elif any(word in text for word in ['failed', 'failure', 'error']):
                status = 'FAILED'
            elif any(word in text for word in ['skipped', 'pending']):
                status = 'SKIPPED'
            
            # Only add if we found a status
            if status:
                test_case = {
                    'name': name.strip(),
                    'status': status,
                    'error': None
                }
                
                # If failed, try to find error details
                if status == 'FAILED':
                    error_elems = elem.find_all(['pre', 'code', 'div'])
                    error_text = ' '.join(e.get_text().strip() for e in error_elems)
                    if error_text:
                        test_case['error'] = error_text[:1000]
                        
                results.append({'testCase': test_case})
                print(f"Added test case: {name[:50]}... ({status})")
                
    # If no test cases found, use DOM statistics
    if not results:
        print("No test cases found, using text analysis...")
        all_text = text.lower()
        passed_count = all_text.count('passed')
        failed_count = all_text.count('failed')
        skipped_count = all_text.count('skipped')
        
        if passed_count > 0:
            results.append({'testCase': {'name': 'Passed Tests', 'status': 'PASSED', 'error': None}})
        if failed_count > 0:
            results.append({'testCase': {'name': 'Failed Tests', 'status': 'FAILED', 'error': None}})
        if skipped_count > 0:
            results.append({'testCase': {'name': 'Skipped Tests', 'status': 'SKIPPED', 'error': None}})
            
        print(f"Text analysis found: {passed_count} passed, {failed_count} failed, {skipped_count} skipped")
    
    print(f"Final results: {len(results)} test cases")
    return results
 
def parse_messages(messages):
    print("\nParsing Cucumber messages...")
    
    results = {
        'total': 0,
        'passed': 0,
        'failed': 0,
        'skipped': 0,
        'failures': []
    }
    
    # Phase 1: Build execution maps
    pickles = {}           # pickle_id -> name
    test_cases = {}       # test_case_id -> pickle_id
    started_cases = {}    # started_id -> test_case_id
    case_steps = {}       # started_id -> list of step results
    errors = {}           # started_id -> first error message
    
    for msg in messages:
        if not isinstance(msg, dict):
            continue
            
        if 'pickle' in msg:
            pickle = msg['pickle']
            if 'id' in pickle and 'name' in pickle:
                pickles[pickle['id']] = pickle['name']
                print(f"Found scenario: {pickle['name']}")
                
        elif 'testCase' in msg:
            test_case = msg['testCase']
            if 'id' in test_case and 'pickleId' in test_case:
                test_cases[test_case['id']] = test_case['pickleId']
                
        elif 'testCaseStarted' in msg:
            started = msg['testCaseStarted']
            if 'id' in started and 'testCaseId' in started:
                started_id = started['id']
                started_cases[started_id] = started['testCaseId']
                case_steps[started_id] = []
                
        elif 'testStepFinished' in msg:
            step = msg['testStepFinished']
            started_id = step.get('testCaseStartedId')
            if started_id:
                result = step.get('testStepResult', {})
                status = result.get('status', '').upper()
                if status:
                    case_steps[started_id].append(status)
                    if status == 'FAILED' and started_id not in errors:
                        error = result.get('message', '')
                        if error:
                            errors[started_id] = error
                            print(f"Found error: {error[:100]}...")
    
    print(f"\nFound {len(pickles)} scenarios")
    
    # Phase 2: Calculate test results
    processed = set()
    for started_id, steps in case_steps.items():
        if not steps or started_id in processed:
            continue
            
        processed.add(started_id)
        test_case_id = started_cases.get(started_id)
        pickle_id = test_cases.get(test_case_id)
        name = pickles.get(pickle_id, 'Unknown Scenario')
        
        # Determine overall status
        if 'FAILED' in steps:
            status = 'FAILED'
        elif all(s == 'SKIPPED' for s in steps):
            status = 'SKIPPED'
        elif all(s in ('PASSED', 'UNDEFINED', 'AMBIGUOUS') for s in steps):
            status = 'PASSED'
        else:
            continue  # Skip if we can't determine status
            
        results['total'] += 1
        if status == 'PASSED':
            results['passed'] += 1
            print(f"Scenario passed: {name}")
        elif status == 'FAILED':
            results['failed'] += 1
            print(f"Scenario failed: {name}")
            results['failures'].append({
                'name': name,
                'error': errors.get(started_id, 'Test failed with no error message')
            })
        elif status == 'SKIPPED':
            results['skipped'] += 1
            print(f"Scenario skipped: {name}")
    
    print(f"\nFinal results - Total: {results['total']}, Passed: {results['passed']}, Failed: {results['failed']}, Skipped: {results['skipped']}")
    return results
    
    print(f"\nFinal results - Total: {results['total']}, Passed: {results['passed']}, Failed: {results['failed']}, Skipped: {results['skipped']}")
    return results
    
    print(f"\nFinal results - Total: {results['total']}, Passed: {results['passed']}, Failed: {results['failed']}, Skipped: {results['skipped']}")
    return results
    
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
    """Parse the HTML file directly using BeautifulSoup when other methods fail"""
    if BeautifulSoup is None:
        raise RuntimeError("BeautifulSoup not installed. Install from requirements.txt")
    with open(html_path, 'r', encoding='utf-8', errors='ignore') as fh:
        text = fh.read()
        
    # Try to find test results in HTML
    messages = parse_cucumber_messages_from_html(text)
    if messages:
        return parse_messages(messages)
    
    # If no structured data found, try a more aggressive search
    soup = BeautifulSoup(text, 'lxml')
    
    results = {
        'total': 0,
        'passed': 0,
        'failed': 0,
        'skipped': 0,
        'failures': []
    }
    
    # Look for elements that might indicate test results
    all_text = soup.get_text().lower()
    
    # Count keyword occurrences as a last resort
    results['passed'] = all_text.count('passed')
    results['failed'] = all_text.count('failed')
    results['skipped'] = all_text.count('skipped')
    results['total'] = results['passed'] + results['failed'] + results['skipped']
    
    # Try to find failure messages
    error_containers = soup.find_all(['pre', 'code', 'div'], 
                                   text=re.compile(r'error|exception|fail', re.I))
    
    for container in error_containers:
        error_text = container.get_text().strip()
        if error_text:
            results['failures'].append({
                'name': 'Unknown Test',
                'error': error_text[:1000]
            })
            
    return results
 
def aggregate_reports(paths):
    total_results = {
        'total': 0,
        'passed': 0,
        'failed': 0,
        'skipped': 0,
        'failures': [],
        'files_parsed': 0
    }
 
    for p in paths:
        total_results['files_parsed'] += 1
        text = p.read_text(encoding='utf-8', errors='ignore')
        messages = parse_cucumber_messages_from_html(text)
        if messages:
            res = parse_messages(messages)
            # Update totals
            total_results['total'] += res['total']
            total_results['passed'] += res['passed']
            total_results['failed'] += res['failed']
            total_results['skipped'] += res['skipped']
            # Add failures with file info
            for failure in res['failures']:
                total_results['failures'].append({
                    'file': str(p.name),
                    **failure
                })
        else:
            # fallback DOM parsing
            res = fallback_dom_parse(p)
            total_results['total'] += res['total']
            total_results['passed'] += res['passed']
            total_results['failed'] += res['failed']
            total_results['skipped'] += res['skipped']
            for failure in res['failures']:
                total_results['failures'].append({
                    'file': str(p.name),
                    **failure
                })
    
    return total_results
 
def write_outputs(agg, json_out_path, md_path='summary.md'):
    with open(json_out_path, 'w', encoding='utf-8') as fh:
        json.dump(agg, fh, indent=2, ensure_ascii=False)
 
    # Calculate pass percentage
    total = agg.get('total', 0)
    passed = agg.get('passed', 0)
    failed = agg.get('failed', 0)
    skipped = agg.get('skipped', 0)
    pass_rate = (passed / total * 100) if total > 0 else 0
    
    # markdown summary
    md = []
    md.append("# Test Execution Summary\n")
    md.append(f"- Files parsed: {agg.get('files_parsed', 1)}")
    md.append(f"- Total tests: {total}")
    md.append(f"- Pass rate: {pass_rate:.1f}%")
    md.append(f"- Results breakdown:")
    md.append(f"  - ✅ Passed: {passed}")
    md.append(f"  - ❌ Failed: {failed}")
    md.append(f"  - ⚠️ Skipped: {skipped}\n")
    
    # Add failure details
    if agg.get('failures'):
        md.append("## Failed Tests")
        for i, failure in enumerate(agg.get('failures', []), 1):
            md.append(f"\n### {i}. {failure.get('name', 'Unnamed Test')}")
            if failure.get('error'):
                # Format error message for better readability
                error_lines = failure['error'].splitlines()
                if len(error_lines) > 1:
                    md.append("\n<details>")
                    md.append("<summary>Error Details</summary>\n")
                    md.append("```")
                    md.extend(error_lines[:20])  # Show first 20 lines
                    if len(error_lines) > 20:
                        md.append("...")
                    md.append("```")
                    md.append("</details>")
                else:
                    md.append(f"\nError: `{failure['error']}`")
    
    with open(md_path, 'w', encoding='utf-8') as fh:
        fh.write("\n".join(md))
 
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