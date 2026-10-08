"""Profile-local Chief of Staff watchdog; never modifies the shared scheduler."""
import json
import os
from pathlib import Path
import signal
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

JOB_ID = 'b7dee36991a7'
LIMIT_SECONDS = 1800


def run_bounded(command, log_path, timeout):
    with open(log_path, 'w') as output:
        child = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, start_new_session=True)
        status = 'FINISHED'
        try:
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            status = 'PARTIAL'
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        if child.returncode != 0:
            status = 'PARTIAL'
        return {'status': status, 'returncode': child.returncode}


def main():
    home = Path(os.environ['HERMES_HOME']).resolve()
    if home.name != 'fuzzys':
        raise RuntimeError('This watchdog must run in the fuzzys profile')
    job = next(j for j in json.loads((home / 'cron/jobs.json').read_text())['jobs']
               if j['id'] == JOB_ID)
    now = datetime.now(ZoneInfo('America/Los_Angeles'))
    run = home / 'workspaces/chief-of-staff/bounded-runs' / now.strftime('%Y-%m-%d_%H%M%S_%f')
    run.mkdir(parents=True)
    log = run / 'worker.log'
    brief = run / 'brief.md'
    prompt = job['prompt'] + '\nSave the complete final brief at this exact local path: ' + str(brief)
    command = [str(Path.home() / '.local/bin/hermes'), '-p', 'fuzzys',
               '--skills', 'fuzzys-master-skill', '--in', str(run), 'chat',
               '--oneshot', '--run-budget', '1200', '--max-turns', '45', '-q', prompt]
    result = run_bounded(command, log, LIMIT_SECONDS)
    result.update({'started_at_pacific': now.isoformat(), 'finished_at_pacific':
                   datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(),
                   'limit_seconds': LIMIT_SECONDS, 'worker_log': str(log), 'brief': str(brief)})
    if not brief.exists() or not brief.read_text().strip():
        result['status'] = 'PARTIAL'
    (run / 'status.json').write_text(json.dumps(result, indent=2) + '\n')
    if result['status'] == 'PARTIAL':
        print('# Chief of Staff: PARTIAL\n')
        print('The bounded worker timed out, failed, or did not save a final brief. This is not a completed source review.')
        print('Preserved worker log: ' + str(log))
        print('Status record: ' + str(run / 'status.json'))
        if brief.exists():
            print('\n## Preserved candidate; not verified final\n')
            print(brief.read_text())
        raise SystemExit(2)
    else:
        print(brief.read_text())


if __name__ == '__main__':
    main()
