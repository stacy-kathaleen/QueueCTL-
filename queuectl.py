#!/usr/bin/env python3
"""
QueueCTL - CLI-based Background Job Queue System
Main entry point for the CLI application
"""

import click
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

from queue_manager import QueueManager
from worker import Worker
from config import Config

# Initialize paths
BASE_DIR = Path.home() / ".queuectl"
BASE_DIR.mkdir(exist_ok=True)

queue_manager = QueueManager(BASE_DIR / "jobs.db")
config = Config(BASE_DIR / "config.json")


@click.group()
def cli():
    """QueueCTL - Background Job Queue System"""
    pass


@cli.command()
@click.argument('job_json')
def enqueue(job_json):
    """Enqueue a new job. Example: queuectl enqueue '{"id":"job1","command":"sleep 2"}'"""
    try:
        job_data = json.loads(job_json)
        
        if 'id' not in job_data or 'command' not in job_data:
            click.echo("Error: Job must have 'id' and 'command' fields", err=True)
            sys.exit(1)
        
        # Set defaults
        job_data.setdefault('state', 'pending')
        job_data.setdefault('attempts', 0)
        job_data.setdefault('max_retries', config.get('max_retries'))
        job_data.setdefault('created_at', datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'))
        job_data.setdefault('updated_at', datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'))
        
        queue_manager.enqueue_job(job_data)
        click.echo(f"[OK] Job '{job_data['id']}' enqueued successfully")
        
    except json.JSONDecodeError:
        click.echo("Error: Invalid JSON format", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@cli.group()
def worker():
    """Manage worker processes"""
    pass


@worker.command()
@click.option('--count', default=1, help='Number of workers to start')
def start(count):
    """Start worker processes"""
    import os
    if os.name == 'nt':  # Windows
        click.echo("Warning: Multiple workers not fully supported on Windows.")
        click.echo("  Starting single worker instead. Use Ctrl+C to stop.")
        count = 1
    
    click.echo(f"Starting {count} worker(s)...")
    
    workers = []
    try:
        for i in range(count):
            w = Worker(
                worker_id=f"worker-{i+1}",
                queue_manager=queue_manager,
                config=config,
                base_dir=BASE_DIR
            )
            w.start()
            workers.append(w)
            click.echo(f"[OK] Worker {i+1} started")
        
        if count == 1:
            click.echo(f"\nWorker running. Press Ctrl+C to stop gracefully.")
        else:
            click.echo(f"\n{count} worker(s) running. Press Ctrl+C to stop gracefully.")
        
        # Wait for workers
        for w in workers:
            w.join()
            
    except KeyboardInterrupt:
        click.echo("\n\nShutting down workers gracefully...")
        for w in workers:
            w.stop()
        click.echo("[OK] All workers stopped")


@worker.command()
def stop():
    """Stop all running workers"""
    pid_file = BASE_DIR / "workers.pid"
    
    if not pid_file.exists():
        click.echo("No workers running")
        return
    
    import signal
    import os
    
    with open(pid_file, 'r') as f:
        pids = [int(line.strip()) for line in f if line.strip()]
    
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            click.echo(f"[OK] Sent stop signal to worker (PID: {pid})")
        except ProcessLookupError:
            click.echo(f"[WARN] Worker (PID: {pid}) not found")
    
    pid_file.unlink()


@cli.command()
def status():
    """Show summary of job states and active workers"""
    stats = queue_manager.get_stats()
    
    click.echo("\n=== QueueCTL Status ===\n")
    click.echo("Job States:")
    click.echo(f"  Pending:    {stats['pending']}")
    click.echo(f"  Processing: {stats['processing']}")
    click.echo(f"  Completed:  {stats['completed']}")
    click.echo(f"  Failed:     {stats['failed']}")
    click.echo(f"  Dead (DLQ): {stats['dead']}")
    click.echo(f"\n  Total Jobs: {stats['total']}")
    
    # Worker info
    pid_file = BASE_DIR / "workers.pid"
    if pid_file.exists():
        with open(pid_file, 'r') as f:
            active_workers = len([l for l in f if l.strip()])
        click.echo(f"\nActive Workers: {active_workers}")
    else:
        click.echo("\nActive Workers: 0")


@cli.command()
@click.option('--state', help='Filter by state (pending, processing, completed, failed, dead)')
@click.option('--limit', default=20, help='Maximum number of jobs to display')
def list(state, limit):
    """List jobs by state"""
    jobs = queue_manager.list_jobs(state, limit)
    
    if not jobs:
        click.echo(f"No jobs found" + (f" with state '{state}'" if state else ""))
        return
    
    click.echo(f"\n{'ID':<20} {'State':<12} {'Command':<30} {'Attempts':<10} {'Updated':<20}")
    click.echo("=" * 100)
    
    for job in jobs:
        cmd = job['command'][:27] + '...' if len(job['command']) > 30 else job['command']
        updated = job['updated_at'][:19] if job['updated_at'] else 'N/A'
        click.echo(f"{job['id']:<20} {job['state']:<12} {cmd:<30} {job['attempts']:<10} {updated:<20}")


@cli.group()
def dlq():
    """Manage Dead Letter Queue"""
    pass


@dlq.command()
@click.option('--limit', default=20, help='Maximum number of jobs to display')
def list(limit):
    """List jobs in DLQ"""
    jobs = queue_manager.list_jobs('dead', limit)
    
    if not jobs:
        click.echo("DLQ is empty")
        return
    
    click.echo(f"\n{'ID':<20} {'Command':<30} {'Attempts':<10} {'Updated':<20}")
    click.echo("=" * 90)
    
    for job in jobs:
        cmd = job['command'][:27] + '...' if len(job['command']) > 30 else job['command']
        updated = job['updated_at'][:19] if job['updated_at'] else 'N/A'
        click.echo(f"{job['id']:<20} {cmd:<30} {job['attempts']:<10} {updated:<20}")


@dlq.command()
@click.argument('job_id')
def retry(job_id):
    """Retry a job from DLQ"""
    try:
        queue_manager.retry_dlq_job(job_id)
        click.echo(f"[OK] Job '{job_id}' moved back to queue for retry")
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@cli.group()
def config_cmd():
    """Manage configuration"""
    pass


@config_cmd.command(name='set')
@click.argument('key')
@click.argument('value')
def config_set(key, value):
    """Set configuration value. Example: queuectl config set max-retries 3"""
    try:
        # Convert to appropriate type
        if value.isdigit():
            value = int(value)
        elif value.replace('.', '', 1).isdigit():
            value = float(value)
        
        config.set(key.replace('-', '_'), value)
        click.echo(f"[OK] Configuration updated: {key} = {value}")
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@config_cmd.command(name='get')
@click.argument('key', required=False)
def config_get(key):
    """Get configuration value(s)"""
    if key:
        value = config.get(key.replace('-', '_'))
        click.echo(f"{key}: {value}")
    else:
        click.echo("\nCurrent Configuration:")
        click.echo("=" * 40)
        for k, v in config.get_all().items():
            click.echo(f"  {k.replace('_', '-')}: {v}")


if __name__ == '__main__':
    cli()
