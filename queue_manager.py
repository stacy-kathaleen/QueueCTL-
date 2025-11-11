"""
Queue Manager - Handles job persistence and state management
"""

import sqlite3
import json
from datetime import datetime
from threading import Lock
from pathlib import Path


class QueueManager:
    """Manages job queue with SQLite persistence"""
    
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.lock = Lock()
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                command TEXT NOT NULL,
                state TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                next_retry_at TEXT,
                error_message TEXT,
                output TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def enqueue_job(self, job_data):
        """Add a new job to the queue"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    INSERT INTO jobs (id, command, state, attempts, max_retries, 
                                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    job_data['id'],
                    job_data['command'],
                    job_data.get('state', 'pending'),
                    job_data.get('attempts', 0),
                    job_data.get('max_retries', 3),
                    job_data['created_at'],
                    job_data['updated_at']
                ))
                
                conn.commit()
            except sqlite3.IntegrityError:
                raise Exception(f"Job with id '{job_data['id']}' already exists")
            finally:
                conn.close()
    
    def get_next_job(self, worker_id):
        """Get next pending job and mark as processing"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            try:
                # Get jobs that are pending or failed with retry time passed
                now = datetime.utcnow().isoformat() + 'Z'
                
                cursor.execute('''
                    SELECT * FROM jobs 
                    WHERE state = 'pending' 
                       OR (state = 'failed' AND (next_retry_at IS NULL OR next_retry_at <= ?))
                    ORDER BY created_at ASC
                    LIMIT 1
                ''', (now,))
                
                row = cursor.fetchone()
                
                if row:
                    job = dict(row)
                    
                    # Mark as processing
                    cursor.execute('''
                        UPDATE jobs 
                        SET state = 'processing', updated_at = ?
                        WHERE id = ?
                    ''', (now, job['id']))
                    
                    conn.commit()
                    return job
                
                return None
                
            finally:
                conn.close()
    
    def update_job(self, job_id, updates):
        """Update job fields"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                updates['updated_at'] = datetime.utcnow().isoformat() + 'Z'
                
                set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
                values = list(updates.values()) + [job_id]
                
                cursor.execute(f'''
                    UPDATE jobs SET {set_clause}
                    WHERE id = ?
                ''', values)
                
                conn.commit()
            finally:
                conn.close()
    
    def get_job(self, job_id):
        """Get job by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM jobs WHERE id = ?', (job_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    def list_jobs(self, state=None, limit=20):
        """List jobs, optionally filtered by state"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            if state:
                cursor.execute('''
                    SELECT * FROM jobs WHERE state = ? 
                    ORDER BY updated_at DESC LIMIT ?
                ''', (state, limit))
            else:
                cursor.execute('''
                    SELECT * FROM jobs 
                    ORDER BY updated_at DESC LIMIT ?
                ''', (limit,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    def get_stats(self):
        """Get job statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT state, COUNT(*) as count 
                FROM jobs 
                GROUP BY state
            ''')
            
            stats = {
                'pending': 0,
                'processing': 0,
                'completed': 0,
                'failed': 0,
                'dead': 0,
                'total': 0
            }
            
            for row in cursor.fetchall():
                state, count = row
                stats[state] = count
                stats['total'] += count
            
            return stats
        finally:
            conn.close()
    
    def retry_dlq_job(self, job_id):
        """Move job from DLQ back to pending"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    SELECT state FROM jobs WHERE id = ?
                ''', (job_id,))
                
                row = cursor.fetchone()
                
                if not row:
                    raise Exception(f"Job '{job_id}' not found")
                
                if row[0] != 'dead':
                    raise Exception(f"Job '{job_id}' is not in DLQ (current state: {row[0]})")
                
                now = datetime.utcnow().isoformat() + 'Z'
                cursor.execute('''
                    UPDATE jobs 
                    SET state = 'pending', attempts = 0, next_retry_at = NULL, 
                        updated_at = ?, error_message = NULL
                    WHERE id = ?
                ''', (now, job_id))
                
                conn.commit()
            finally:
                conn.close()