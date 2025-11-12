# QueueCTL - Background Job Queue System

A production-grade CLI-based job queue system with worker processes, automatic retry with exponential backoff, and Dead Letter Queue (DLQ) support.

# Features

- CLI-based job management
-  Multiple concurrent workers
-  Automatic retry with exponential backoff
-  Dead Letter Queue (DLQ) for failed jobs
-  SQLite persistence (survives restarts)
-  Configurable retry and backoff settings
-  Job locking to prevent duplicate processing
-  Graceful worker shutdown

# Requirements

- Python 3.7+
- pip

# Installation & Setup

## 1. Clone or Download Files

Save all the provided files in a directory:
```
queuectl/
├── queuectl.py
├── queue_manager.py
├── worker.py
├── config.py
├── add_job.py
├── clear_db.py
└── README.md
```

## 2. Install Dependencies

**Windows:**
```bash
python -m pip install click
```

**Linux/Mac:**
```bash
pip3 install click
```

## 3. Verify Installation

```bash
# Windows
python queuectl.py --help

# Linux/Mac
python3 queuectl.py --help
```

## 4. Clear Database (if needed)

If you get "Job already exists" errors:
```bash
python clear_db.py
```

# Usage Examples

## 1. Enqueue Jobs

**Windows:**
```bash
# Simple command
python queuectl.py enqueue "{\"id\":\"job1\",\"command\":\"echo Hello World\"}"

# Sleep job (use timeout on Windows instead of sleep)
python queuectl.py enqueue "{\"id\":\"job2\",\"command\":\"timeout /t 5 /nobreak\"}"

# Python script
python queuectl.py enqueue "{\"id\":\"job3\",\"command\":\"python script.py\"}"
```

**Linux/Mac:**
```bash
# Simple command
python3 queuectl.py enqueue '{"id":"job1","command":"echo Hello World"}'

# Sleep job
python3 queuectl.py enqueue '{"id":"job2","command":"sleep 5"}'

# Job with custom retries
python3 queuectl.py enqueue '{"id":"job3","command":"python script.py","max_retries":5}'
```

## 2. Start Workers

```bash
# Windows
python queuectl.py worker start
python queuectl.py worker start --count 3

# Linux/Mac
python3 queuectl.py worker start
python3 queuectl.py worker start --count 3
```

**To stop workers:**
- Press `Ctrl+C` (workers will finish their current job before stopping)
- If Ctrl+C doesn't work, press it **twice quickly**
- On Windows, you can also use `Ctrl+Break`
- Or simply close the terminal window

Workers will run until you stop them or they crash.

## 3. Check Status

```bash
# Windows
python queuectl.py status

# Linux/Mac
python3 queuectl.py status
```

Output:
```
=== QueueCTL Status ===

Job States:
  Pending:    2
  Processing: 1
  Completed:  5
  Failed:     0
  Dead (DLQ): 1

  Total Jobs: 9

Active Workers: 3
```

## 4. List Jobs

```bash
# List all jobs (last 20)
python3 queuectl.py list

# List by state
python3 queuectl.py list --state pending
python3 queuectl.py list --state completed
python3 queuectl.py list --state failed

# List with custom limit
python3 queuectl.py list --limit 50
```

## 5. Manage DLQ

```bash
# List jobs in DLQ
python3 queuectl.py dlq list

# Retry a failed job from DLQ
python3 queuectl.py dlq retry job1
```

## 6. Configuration

```bash
# Set max retries
python3 queuectl.py config set max-retries 5

# Set backoff base (delay = base ^ attempts)
python3 queuectl.py config set backoff-base 3

# View configuration
python3 queuectl.py config get
python3 queuectl.py config get max-retries
```

# Architecture Overview

## Components

1. **QueueCTL (queuectl.py)**: Main CLI interface using Click framework
2. **QueueManager (queue_manager.py)**: Handles job persistence and state management with SQLite
3. **Worker (worker.py)**: Executes jobs using multiprocessing
4. **Config (config.py)**: Manages persistent configuration

## Job Lifecycle

```
pending → processing → completed
    ↓          ↓
  failed  →  [retry with backoff]
    ↓
  dead (DLQ)
```

## Job States

| State | Description |
|-------|-------------|
| `pending` | Waiting to be picked up by a worker |
| `processing` | Currently being executed by a worker |
| `completed` | Successfully executed |
| `failed` | Failed but will retry |
| `dead` | Permanently failed (in DLQ) |

## Retry Mechanism

- **Exponential Backoff**: `delay = backoff_base ^ attempts` seconds
- Default: `base = 2`, so delays are 2s, 4s, 8s, etc.
- After `max_retries` attempts, job moves to DLQ
- Configurable via `config set` commands

## Concurrency & Locking

- SQLite with file locking prevents duplicate job processing
- Workers use transaction-based locking to claim jobs
- Multiple workers can run safely in parallel

## Data Persistence

- All job data stored in `~/.queuectl/jobs.db` (SQLite)
- Configuration in `~/.queuectl/config.json`
- Worker PIDs in `~/.queuectl/workers.pid`
- Survives system restarts

# Testing

## Run Automated Tests

```bash
./test_queuectl.sh
```

This validates:
- Configuration management
- Job enqueuing
- Worker processing
- Retry mechanism
- DLQ operations
- Data persistence

## Manual Testing Scenarios

### Test 1: Basic Job Execution
```bash
python3 queuectl.py enqueue '{"id":"test1","command":"echo Success"}'
python3 queuectl.py worker start
# Press Ctrl+C after a few seconds
python3 queuectl.py list --state completed
```

### Test 2: Failed Job with Retry
```bash
python3 queuectl.py config set max-retries 2
python3 queuectl.py enqueue '{"id":"fail-test","command":"exit 1"}'
python3 queuectl.py worker start
# Watch it retry and move to DLQ
python3 queuectl.py dlq list
```

### Test 3: Multiple Workers
```bash
# Enqueue multiple jobs
for i in {1..10}; do
  python3 queuectl.py enqueue "{\"id\":\"job$i\",\"command\":\"sleep 2\"}"
done

# Start 3 workers and watch parallel processing
python3 queuectl.py worker start --count 3
```

### Test 4: Persistence
```bash
python3 queuectl.py enqueue '{"id":"persist","command":"echo Test"}'
python3 queuectl.py list
# Restart terminal/system
python3 queuectl.py list  # Job still there
```

# Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `max_retries` | 3 | Maximum retry attempts before DLQ |
| `backoff_base` | 2 | Base for exponential backoff calculation |
| `worker_timeout` | 300 | Job timeout in seconds (5 minutes) |

# Assumptions & Trade-offs

## Assumptions
- Jobs are shell commands (executed via `subprocess`)
- Exit code 0 = success, non-zero = failure
- Single machine deployment (not distributed)
- Moderate job volume (thousands, not millions)

## Trade-offs
- **SQLite vs Redis/PostgreSQL**: Chose SQLite for simplicity and zero external dependencies. For high-throughput production, consider Redis or PostgreSQL.
- **File locking**: Sufficient for single-machine use. Distributed setup would need a proper message broker.
- **No job priorities**: All jobs processed FIFO. Priority queues would require additional complexity.
- **Subprocess execution**: Secure for trusted commands. Add sandboxing for untrusted input.

# Sample Output

## Status Command
```
=== QueueCTL Status ===

Job States:
  Pending:    5
  Processing: 2
  Completed:  15
  Failed:     1
  Dead (DLQ): 2

  Total Jobs: 25

Active Workers: 3
```

## List Command
```
ID                   State        Command                        Attempts   Updated             
====================================================================================================
job-123              pending      echo Hello World               0          2025-11-04T10:30:...
job-456              processing   sleep 10                       0          2025-11-04T10:31:...
job-789              completed    python script.py               0          2025-11-04T10:29:...
```

# Troubleshooting

## Jobs not processing
- Check if workers are running: `python3 queuectl.py status`
- Check for stuck jobs: `python3 queuectl.py list --state processing`

## Worker won't start
- Check for stale PID file: `rm ~/.queuectl/workers.pid`
- Ensure no port conflicts or resource limits

## Database locked errors
- Usually transient; workers retry automatically
- If persistent, check file permissions on `~/.queuectl/`

# Demo Video
- https://drive.google.com/file/d/1PzUJbfg6qkTUMbqBL1XOoT6Vc7JHMPWH/view?usp=sharing
