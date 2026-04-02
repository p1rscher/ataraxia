import os
import sys
import time
import logging

logger = logging.getLogger(__name__)

LOCK_FILE = "bot.lock"

class ProcessLock:
    def __init__(self):
        self.lock_acquired = False
    
    def acquire(self, timeout=60):
        """
        Trys to get lock as long as the timeout has not been reached.
        Returns True if the lock has been applied successfully, False if not.
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if not os.path.exists(LOCK_FILE):
                # Create Lock File with PID
                try:
                    with open(LOCK_FILE, 'w') as f:
                        f.write(str(os.getpid()))
                    self.lock_acquired = True
                    logger.info(f"Process lock acquired (PID: {os.getpid()})")
                    return True
                except Exception as e:
                    logger.error(f"Failed to create lock file: {e}")
                    return False
            else:
                # Lock is existent
                try:
                    with open(LOCK_FILE, 'r') as f:
                        old_pid = int(f.read().strip())

                    if not self._is_process_running(old_pid):

                        logger.warning(f"Removing stale lock file (dead PID: {old_pid})")
                        os.remove(LOCK_FILE)
                        continue
                    
                    logger.info(f"Waiting for old instance to shutdown (PID: {old_pid})...")
                    time.sleep(1)
                    
                except Exception as e:
                    logger.warning(f"Error reading lock file: {e}, removing it")
                    try:
                        os.remove(LOCK_FILE)
                    except:
                        pass
        
        logger.error(f"Timeout: Could not acquire lock after {timeout} seconds")
        return False
    
    def release(self):
        """Gibt Lock frei"""
        if self.lock_acquired and os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
                logger.info(f"Process lock released (PID: {os.getpid()})")
            except Exception as e:
                logger.warning(f"Failed to remove lock file: {e}")
    
    def _is_process_running(self, pid):
        """Prüft ob Prozess mit gegebener PID läuft (Windows & Linux)"""
        try:
            if sys.platform == "win32":
                # Windows: use tasklist
                import subprocess
                output = subprocess.check_output(
                    f'tasklist /FI "PID eq {pid}"',
                    shell=True,
                    text=True
                )
                return str(pid) in output
            else:
                # Linux/Unix: os.kill with signal 0
                os.kill(pid, 0)
                return True
        except:
            return False
    
    def __enter__(self):
        if not self.acquire():
            sys.exit(1)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
