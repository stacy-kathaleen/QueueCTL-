"""
Worker - Executes jobs from the queue
"""

import subprocess
import time
from datetime import datetime, timedelta, timezone
from threading import Thread, Event
import signal
import sys


class Worker:
    """Worker process that executes jobs"""
    
    def __init__(self, worker_id, queue_manager, config, base_dir):
        self.worker_id = worker_id
        self.queue_manager = queue_manager
        self.config = config
        self.base_dir = base_dir
        self.thread = None
        self.stop_event = Event()
        self.running = False
    
    def start(self):
        """Start the worker thread"""
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop the worker thread gracefully"""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)
    
    def join(self):
        """Wait for worker to finish"""
        if self.thread:
            self.thread.join()
    
    def _run(self):
        """Main worker loop"""
        self.running = True
        
        print(f"[{self.worker_id}] Worker started")
        
        while self.running and not self.stop_event.is_set():
            try:
                job = self.queue_manager.get_next_job(self.worker_id)
                
                if job:
                    self._execute_job(job)
                else:
                    time.sleep(1)  # No jobs available, wait
                    
            except KeyboardInterrupt:
                print(f"\n[{self.worker_id}] Received shutdown signal, finishing current job...")
                self.running = False
                break
            except Exception as e:
                print(f"[{self.worker_id}] Error in worker loop: {e}")
                time.sleep(1)
        
        print(f"[{self.worker_id}] Worker stopped")
    
    def _execute_job(self, job):
        """Execute a single job"""
        job_id = job['id']
        command = job['command']
        
        print(f"[{self.worker_id}] Processing job '{job_id}': {command}")
        
        try:
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                # Job succeeded
                print(f"[{self.worker_id}] Job '{job_id}' completed successfully")
                self.queue_manager.update_job(job_id, {
                    'state': 'completed',
                    'output': result.stdout
                })
            else:
                # Job failed
                self._handle_failure(job, f"Command exited with code {result.returncode}: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            self._handle_failure(job, "Job timed out after 5 minutes")
        except Exception as e:
            self._handle_failure(job, f"Execution error: {str(e)}")
    
    def _handle_failure(self, job, error_message):
        """Handle job failure with retry logic"""
        job_id = job['id']
        attempts = job['attempts'] + 1
        max_retries = job['max_retries']
        
        print(f"[{self.worker_id}] Job '{job_id}' failed (attempt {attempts}/{max_retries}): {error_message}")
        
        if attempts >= max_retries:
            # Move to DLQ
            print(f"[{self.worker_id}] Job '{job_id}' moved to DLQ after {attempts} attempts")
            self.queue_manager.update_job(job_id, {
                'state': 'dead',
                'attempts': attempts,
                'error_message': error_message
            })
        else:
            # Schedule retry with exponential backoff
            backoff_base = self.config.get('backoff_base')
            delay = backoff_base ** attempts
            next_retry_at = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat().replace('+00:00', 'Z')
            
            print(f"[{self.worker_id}] Job '{job_id}' will retry in {delay} seconds")
            
            self.queue_manager.update_job(job_id, {
                'state': 'failed',
                'attempts': attempts,
                'next_retry_at': next_retry_at,
                'error_message': error_message
            })
