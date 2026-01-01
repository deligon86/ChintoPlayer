import threading
import time
from datetime import datetime, timedelta
from typing import Callable, List, Dict, Any
from core import logger


class Scheduler:
    """
    Task scheduler for handling one time and recurring tasks
    """
    def __init__(self):
        self.jobs: List[Dict[str, Any]] = []
        self.running = False
        self.delay = 0.1
        self._lock = threading.RLock()

    def start_loop(self):
        """
        Starts the scheduler
        :return:
        """
        if self.running:
            return
        self.running = True
        thread = threading.Thread(target=self._run_loop, daemon=True, name="AppScheduler")
        thread.start()

    def _run_loop(self):
        while self.running:
            now = datetime.now()
            jobs_to_run = []

            with self._lock:
                # Filter out jobs that are due
                pending_jobs = []
                for job in self.jobs:
                    if now >= job['time']:
                        jobs_to_run.append(job)
                    else:
                        pending_jobs.append(job)

                self.jobs = pending_jobs

            for job in jobs_to_run:
                try:
                    self._execute_job(job['name'], job['func'], *job['args'])
                    logger.info(f"[Scheduler] Dispatched job: {job['name']}")
                except Exception as e:
                    logger.error(f"[Scheduler] Failed to dispatch {job['name']}: {e}")

                # daily/recurring tasks
                if job.get('daily_time'):
                    job['time'] = self._get_next_daily_time(job['daily_time'])
                    self._requeue_job(job)
                elif job.get('repeat') and job.get('interval'):
                    job['time'] = now + timedelta(seconds=job['interval'])
                    self._requeue_job(job)

            time.sleep(self.delay)

    def _requeue_job(self, job: Dict[str, Any]):
        with self._lock:
            self.jobs.append(job)

    @staticmethod
    def _execute_job(name: str, func: Callable, *args):
        """
        Start job
        :param name:
        :param func:
        :param args:
        :return:
        """
        t = threading.Thread(target=func, args=args, name=f"Job-{name}", daemon=True)
        t.start()

    def add_job(self, name: str, func: Callable, delay_seconds: int, args: tuple = (), unique: bool = False):
        """
        Adds a job. If unique=True, replaces any existing job with the same name (Debounce).

        :param name:
        :param func:
        :param delay_seconds:
        :param unique:
        :param args:
        :return: job
        """
        run_time = datetime.now() + timedelta(seconds=delay_seconds)
        job = {
            "name": name,
            "func": func,
            "args": args,
            "time": run_time,
            "repeat": False,
            "interval": None,
            "daily_time": None
        }

        with self._lock:
            if unique:
                # Remove any existing pending jobs with this name
                self.jobs = [j for j in self.jobs if j['name'] != name]
            self.jobs.append(job)

        return job

    def add_daily_job(self, name: str, func: Callable, time_str: str, args: tuple = ()):
        """
        Add a recurring task
        :param name:
        :param func:
        :param time_str:
        :param args:
        :return:
        """
        run_time = self._get_next_daily_time(time_str)
        job = {
            "name": name,
            "func": func,
            "args": args,
            "time": run_time,
            "repeat": False,
            "interval": None,
            "daily_time": time_str
        }
        with self._lock:
            self.jobs.append(job)
        return job

    def remove_job_by_name(self, name: str):
        """
        Remove the specified job from the schedule
        :param name:
        :return:
        """
        with self._lock:
            self.jobs = [j for j in self.jobs if j['name'] != name]

    @staticmethod
    def _get_next_daily_time(time_str: str):
        hour, minute = map(int, time_str.split(':'))
        now = datetime.now()
        run_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if run_time <= now:
            run_time += timedelta(days=1)
        return run_time

    def stop(self):
        """
        Stops the scheduler
        :return:
        """
        self.running = False