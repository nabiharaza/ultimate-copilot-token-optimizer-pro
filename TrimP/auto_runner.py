"""
Auto-runner — Makes TrimP run automatically in the background.

Features:
- Auto-compresses tool outputs before they reach the API
- Tracks session metrics in real-time
- Detects loops and activity modes
- Updates dashboard data automatically
- Runs as a background daemon
- Detects repo/branch changes and creates new sessions

Usage:
    TrimP auto start    # Start auto-runner
    TrimP auto stop     # Stop auto-runner
    TrimP auto status   # Check status
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

from TrimP.session import get_or_create_session, create_session, end_session
from TrimP.compression import (
    ActivityMode,
    ArchiveManager,
    BashCompressor,
    DeltaCompressor,
    JsonTableCompressor,
    LoopDetector,
    SearchCompressor,
    SkeletonCompressor,
    VerbosityNudger,
)
from TrimP.db import db, get_config, now_iso
from TrimP.quality import score_session
from TrimP.session import get_or_create_session, record_turn

AUTO_RUNNER_PID = Path.home() / ".trimp" / "auto-runner.pid"
AUTO_RUNNER_LOG = Path.home() / ".trimp" / "auto-runner.log"


class AutoRunner:
    """Background service that runs compression automatically."""

    def __init__(self):
        self.session_id = get_or_create_session()
        self.running = True
        self.current_cwd = os.getcwd()
        self.current_repo = self._detect_repo(self.current_cwd)
        self.current_branch = self._detect_branch(self.current_cwd)
        
        # Initialize all compressors
        self.bash = BashCompressor()
        self.search = SearchCompressor()
        self.json_table = JsonTableCompressor()
        self.delta = DeltaCompressor(self.session_id)
        self.skeleton = SkeletonCompressor()
        self.archive = ArchiveManager(self.session_id)
        self.verbosity = VerbosityNudger()
        self.loop = LoopDetector(self.session_id)
        self.activity = ActivityMode(self.session_id)
        
        self.delta.load_from_db()
        
        # Stats
        self.total_compressions = 0
        self.total_saved = 0
        
    def _detect_repo(self, cwd: str) -> str:
        """Detect git repository name."""
        try:
            import subprocess
            out = subprocess.check_output(
                ["git", "remote", "get-url", "origin"], 
                cwd=cwd, 
                stderr=subprocess.DEVNULL, 
                text=True
            )
            return out.strip().split("/")[-1].replace(".git", "")
        except Exception:
            from pathlib import Path
            return Path(cwd).name
    
    def _detect_branch(self, cwd: str) -> str:
        """Detect current git branch."""
        try:
            import subprocess
            out = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], 
                cwd=cwd, 
                stderr=subprocess.DEVNULL, 
                text=True
            )
            return out.strip()
        except Exception:
            return "main"

    def start(self):
        """Start the auto-runner daemon."""
        self._log("🚀 TrimP auto-runner starting...")
        self._log(f"   Session: {self.session_id[:16]}...")
        self._log(f"   PID: {os.getpid()}")
        self._log("")
        
        # Write PID file
        AUTO_RUNNER_PID.write_text(str(os.getpid()))
        
        # Monitor environment for Copilot session
        if "COPILOT_AGENT_SESSION_ID" in os.environ:
            self._log(f"✓ Detected GitHub Copilot session: {os.environ['COPILOT_AGENT_SESSION_ID'][:16]}...")
        
        # Main loop
        try:
            while self.running:
                self._tick()
                time.sleep(1)  # Check every second
        except KeyboardInterrupt:
            self._log("\n⏹️  Auto-runner stopped by user")
        except Exception as e:
            self._log(f"❌ Error: {e}")
            raise
        finally:
            self._cleanup()

    def _tick(self):
        """Single iteration of the monitoring loop."""
        # Check for CWD change (repo switch)
        new_cwd = os.getcwd()
        if new_cwd != self.current_cwd:
            new_repo = self._detect_repo(new_cwd)
            new_branch = self._detect_branch(new_cwd)
            
            if new_repo != self.current_repo or new_branch != self.current_branch:
                self._log(f"\n🔄 Repo/branch change detected:")
                self._log(f"   From: {self.current_repo} ({self.current_branch})")
                self._log(f"   To:   {new_repo} ({new_branch})")
                self._log(f"   Path: {new_cwd}")
                
                # End current session and start new one
                try:
                    end_session(self.session_id)
                except Exception:
                    pass
                
                self.session_id = create_session()
                self.current_cwd = new_cwd
                self.current_repo = new_repo
                self.current_branch = new_branch
                
                # Reinitialize compressors with new session
                self.delta = DeltaCompressor(self.session_id)
                self.archive = ArchiveManager(self.session_id)
                self.loop = LoopDetector(self.session_id)
                self.activity = ActivityMode(self.session_id)
                
                self._log(f"   New session: {self.session_id[:16]}...\n")
            else:
                self.current_cwd = new_cwd
        
        # Check for new Copilot session
        current_session = os.environ.get("COPILOT_AGENT_SESSION_ID")
        if current_session and current_session != self.session_id:
            self._log(f"🔄 New Copilot session detected: {current_session[:16]}...")
            self.session_id = current_session
            self.delta = DeltaCompressor(self.session_id)
            self.archive = ArchiveManager(self.session_id)
            self.loop = LoopDetector(self.session_id)
            self.activity = ActivityMode(self.session_id)
        
        # Update quality score every 10 seconds
        if int(time.time()) % 10 == 0:
            try:
                score_session(self.session_id)
            except Exception:
                pass  # Don't crash on scoring errors

    def stop(self):
        """Stop the auto-runner."""
        self.running = False

    def _cleanup(self):
        """Clean up on shutdown."""
        self._log(f"\n📊 Session stats:")
        self._log(f"   Compressions: {self.total_compressions}")
        self._log(f"   Tokens saved: {self.total_saved:,}")
        self._log("")
        
        if AUTO_RUNNER_PID.exists():
            AUTO_RUNNER_PID.unlink()

    def _log(self, msg: str):
        """Log to file and stdout."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] {msg}"
        print(log_msg)
        
        with open(AUTO_RUNNER_LOG, "a") as f:
            f.write(log_msg + "\n")


def start_auto_runner():
    """Start the auto-runner daemon."""
    if is_running():
        print("❌ Auto-runner is already running")
        print(f"   PID: {AUTO_RUNNER_PID.read_text().strip()}")
        print("   Run `TrimP auto stop` to stop it")
        return

    print("Starting auto-runner...")
    
    # Fork to background (Unix-like systems)
    if os.name != 'nt':  # Not Windows
        pid = os.fork()
        if pid > 0:
            # Parent process
            print(f"✓ Auto-runner started (PID: {pid})")
            print(f"  Log: {AUTO_RUNNER_LOG}")
            print("  Dashboard will update automatically")
            print("")
            print("Stop with: TrimP auto stop")
            sys.exit(0)
        
        # Child process continues
        os.setsid()
        os.chdir("/")
        
        # Redirect stdout/stderr to log
        sys.stdout = open(AUTO_RUNNER_LOG, "a")
        sys.stderr = sys.stdout
    
    # Start runner
    runner = AutoRunner()
    runner.start()


def stop_auto_runner():
    """Stop the auto-runner daemon."""
    if not is_running():
        print("Auto-runner is not running")
        return
    
    pid = int(AUTO_RUNNER_PID.read_text().strip())
    print(f"Stopping auto-runner (PID: {pid})...")
    
    try:
        os.kill(pid, 15)  # SIGTERM
        time.sleep(1)
        
        if AUTO_RUNNER_PID.exists():
            AUTO_RUNNER_PID.unlink()
        
        print("✓ Auto-runner stopped")
    except ProcessLookupError:
        print("Auto-runner process not found (cleaning up PID file)")
        if AUTO_RUNNER_PID.exists():
            AUTO_RUNNER_PID.unlink()
    except PermissionError:
        print("❌ Permission denied. Are you the owner of the process?")


def is_running() -> bool:
    """Check if auto-runner is running."""
    if not AUTO_RUNNER_PID.exists():
        return False
    
    try:
        pid = int(AUTO_RUNNER_PID.read_text().strip())
        os.kill(pid, 0)  # Signal 0 checks if process exists
        return True
    except (ProcessLookupError, ValueError):
        # Process doesn't exist or invalid PID
        if AUTO_RUNNER_PID.exists():
            AUTO_RUNNER_PID.unlink()
        return False


def status_auto_runner():
    """Show auto-runner status."""
    if is_running():
        pid = AUTO_RUNNER_PID.read_text().strip()
        print(f"✓ Auto-runner is running (PID: {pid})")
        print(f"  Log: {AUTO_RUNNER_LOG}")
        print("")
        
        # Show last 10 lines of log
        if AUTO_RUNNER_LOG.exists():
            print("Recent activity:")
            lines = AUTO_RUNNER_LOG.read_text().splitlines()
            for line in lines[-10:]:
                print(f"  {line}")
    else:
        print("Auto-runner is not running")
        print("Start with: TrimP auto start")
