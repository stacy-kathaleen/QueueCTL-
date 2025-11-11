#!/usr/bin/env python3
"""
Helper script to add jobs without quote escaping issues
Usage: python add_job.py <job_id> <command>
"""

import sys
import subprocess
import json

if len(sys.argv) < 3:
    print("Usage: python add_job.py <job_id> <command>")
    print("Example: python add_job.py job1 'echo Hello World'")
    sys.exit(1)

job_id = sys.argv[1]
command = ' '.join(sys.argv[2:])

job_data = {
    "id": job_id,
    "command": command
}

job_json = json.dumps(job_data)

# Call queuectl.py enqueue
result = subprocess.run(
    ['python', 'queuectl.py', 'enqueue', job_json],
    capture_output=True,
    text=True
)

print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)

sys.exit(result.returncode)
