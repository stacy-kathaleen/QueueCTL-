"""
Worker - Executes jobs from the queue
"""

import subprocess
import time
from datetime import datetime, timedelta
from multiprocessing import Process
import signal
import sys


class Worker:
    """Worker process that executes jobs"""
    
    def __init__(self, worker_id, queue_manager, config, base_dir):
        self.worker_id = worker_id
        self.queue_manager = queue_manager
        self.config = config
        self.base_dir = base_dir
        self.process = None
        self.running = False
        self.pid = None
    
    def start(self):
        """Start the worker process"""
        self.process = Process(target=self._run)
        self.process.start()
        self.pid = self.process.pid
        
        # Register PID
        pid_file = self.base_dir / "workers.pid"
        with open(pid_file, 'a') as f:
            f.write(f"{self.pid}\n")
    
    def stop(self):
        """Stop the worker process gracefully"""
        if self.process and self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=10)
            
            if self.process.is_alive():
                self.process.kill()
    
    def join(self):
        """Wait for worker to finish"""
        if self.process:
            self.process.join()
    
    def _run(self):
        """Main worker loop"""
        self.running = True
        
        # Handle graceful shutdown
        def signal_handler(signum, frame):
            print(f"\n[{self.worker_id}] Received shutdown signal, finishing current job...")
            self.running = False
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        print(f"[{self.worker_id}] Worker started")
        
        while self.running:
            try:
                job = self.queue_manager.get_next_job(self.worker_id)
                
                if job:
                    self._execute_job(job)
                else:
                    time.sleep(1)  # No jobs available, wait
                    
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
            next_retry_at = (datetime.utcnow() + timedelta(seconds=delay)).isoformat() + 'Z'
            
            print(f"[{self.worker_id}] Job '{job_id}' will retry in {delay} seconds")
            
            self.queue_manager.update_job(job_id, {
                'state': 'failed',
                'attempts': attempts,
                'next_retry_at': next_retry_at,
                'error_message': error_message
            })