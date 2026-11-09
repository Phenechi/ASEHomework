"""Reproduce a HW2 stage with test outcomes, branch coverage, and source hashes."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
STAGES = {
    'baseline': ['tests.test_workflows'],
    'initial': ['tests.test_workflows', 'tests.hw2.test_initial'],
    'round1': ['tests.test_workflows', 'tests.hw2.test_initial', 'tests.hw2.test_round1'],
    'round2': ['tests.test_workflows', 'tests.hw2.test_initial', 'tests.hw2.test_round1', 'tests.hw2.test_round2'],
    'final': ['tests.test_workflows', 'tests.hw2.test_initial', 'tests.hw2.test_round1', 'tests.hw2.test_round2'],
}


def worker(stage, output):
    sys.path.insert(0, str(ROOT))
    # Set before app import so python-dotenv never loads a real key for this run.
    os.environ['OPENAI_API_KEY'] = ''
    with ExitStack() as stack:
        stack.enter_context(patch('httpx.get', side_effect=AssertionError('Unexpected external HTTP GET')))
        stack.enter_context(patch('httpx.stream', side_effect=AssertionError('Unexpected external download')))
        stack.enter_context(patch('openai.OpenAI', side_effect=AssertionError('Unexpected paid AI request')))
        suite = unittest.defaultTestLoader.loadTestsFromNames(STAGES[stage])
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    outcomes = {'stage': stage, 'tests_run': result.testsRun,
                'successful': result.wasSuccessful(),
                'failures': [{'test': str(test), 'traceback': trace} for test, trace in result.failures],
                'errors': [{'test': str(test), 'traceback': trace} for test, trace in result.errors],
                'skipped': [{'test': str(test), 'reason': reason} for test, reason in result.skipped],
                'expected_failures': len(result.expectedFailures),
                'unexpected_successes': len(result.unexpectedSuccesses)}
    (output / 'test-results.json').write_text(json.dumps(outcomes, indent=2) + '\n', encoding='utf-8')
    return int(not result.wasSuccessful())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=STAGES, required=True)
    parser.add_argument('--output', type=Path, required=True,
                        help='New evidence directory; existing results are never overwritten.')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.worker:
        return worker(args.stage, output)
    if output.exists() and any(output.iterdir()):
        parser.error('Output directory is not empty. Choose a new path to preserve earlier evidence.')
    output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, OPENAI_API_KEY='', PYTHONIOENCODING='utf-8',
               COVERAGE_FILE=str(output / '.coverage'))
    commands = [
        [sys.executable, '-m', 'coverage', 'run', '--rcfile=.coveragerc', '-m', 'scripts.evaluate_tests',
         '--worker', '--stage', args.stage, '--output', str(output)],
        [sys.executable, '-m', 'coverage', 'report'],
        [sys.executable, '-m', 'coverage', 'json', '-o', str(output / 'coverage.json')],
        [sys.executable, '-m', 'coverage', 'html', '-d', str(output / 'html')],
    ]
    runs = []
    for index, command in enumerate(commands):
        try:
            run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True,
                                 encoding='utf-8', errors='replace', timeout=180)
            log = run.stdout + run.stderr
            code = run.returncode
        except subprocess.TimeoutExpired:
            log = 'Evaluation timed out after 180 seconds. No completed test result claimed.\n'
            code = 124
        (output / f'{index + 1:02d}-execution.txt').write_text(log, encoding='utf-8')
        print(log, end='')
        runs.append({'command': command, 'exit_code': code})
        if code == 124 or (index == 0 and not (output / 'test-results.json').exists()):
            break
    files = sorted(set([*ROOT.glob('app/**/*.py'), *ROOT.glob('tests/**/*.py'),
                        ROOT / 'scripts/evaluate_tests.py', ROOT / '.coveragerc',
                        ROOT / 'requirements.txt', ROOT / 'requirements-dev.txt']))
    manifest = {'stage': args.stage, 'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
                'python': sys.version, 'modules': STAGES[args.stage], 'commands': runs,
                'sha256': {str(path.relative_to(ROOT)).replace('\\', '/'):
                           hashlib.sha256(path.read_bytes()).hexdigest() for path in files}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return int(any(run['exit_code'] != 0 for run in runs))


if __name__ == '__main__':
    raise SystemExit(main())
