"""Background download queue with threading."""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from downloader import download_file
from updater import update_watchlist
from models import Anime
from failed_downloads import add_failed, remove_success

logger = logging.getLogger(__name__)


@dataclass
class DownloadJob:
    anime: Anime
    episode: int
    watchlist: list
    destination: Path
    url: str
    status: str = "queued"   # queued, downloading, completed, failed


class DownloadQueue:
    def __init__(self, max_workers=2):
        self.queue = deque()
        self.jobs = {}  # job_id -> DownloadJob
        self.lock = threading.Lock()
        self.workers = []
        self.max_workers = max_workers
        self.running = False
        self.job_counter = 0

    def add_job(self, anime: Anime, episode: int, watchlist: list, destination: Path, url: str) -> int:
        with self.lock:
            self.job_counter += 1
            job = DownloadJob(anime, episode, watchlist, destination, url)
            job_id = self.job_counter
            self.jobs[job_id] = job
            self.queue.append(job_id)
            self._start_workers()
        return job_id

    def _start_workers(self):
        if not self.running:
            self.running = True
            for _ in range(self.max_workers):
                t = threading.Thread(target=self._worker_loop, daemon=True)
                t.start()
                self.workers.append(t)

    def _worker_loop(self):
        while self.running:
            job_id = None
            with self.lock:
                if self.queue:
                    job_id = self.queue.popleft()
            if job_id is not None:
                self._process_job(job_id)
            else:
                time.sleep(0.5)

    def _process_job(self, job_id: int):
        job = self.jobs.get(job_id)
        if not job:
            return
        job.status = "downloading"
        logger.info(f"⏳ Downloading {job.anime.name} episode {job.episode} (job {job_id})")
        success = download_file(job.url, job.destination)
        if success:
            job.status = "completed"
            # Update watchlist
            update_watchlist(job.watchlist, job.anime, job.episode)
            remove_success(job.anime.name, job.episode)
            logger.info(f"✅ Job {job_id} completed")
        else:
            job.status = "failed"
            add_failed(job.anime.name, job.episode)
            logger.error(f"❌ Job {job_id} failed")
        # Remove from active jobs after some time
        # Keep in memory for status display

    def get_status(self):
        with self.lock:
            return {jid: (job.status, job.anime.name, job.episode) for jid, job in self.jobs.items()}

    def shutdown(self):
        self.running = False
        for t in self.workers:
            t.join(timeout=1)