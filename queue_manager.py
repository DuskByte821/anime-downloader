"""Background download queue with watchlist-file propagation."""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from downloader import download_file
from updater import update_watchlist
from failed_downloads import add_failed, remove_success

logger = logging.getLogger(__name__)


@dataclass
class DownloadJob:
    anime: "Anime"
    episode: int
    watchlist: list
    destination: Path
    url: str
    watchlist_file: Optional[Path] = None   # <-- new
    status: str = "queued"


class DownloadQueue:
    def __init__(self, max_workers: int = 2):
        self.queue = deque()
        self.jobs = {}
        self.lock = threading.Lock()
        self.max_workers = max_workers
        self.running = False
        self.job_counter = 0

    def add_job(
        self,
        anime,
        episode: int,
        watchlist: list,
        destination: Path,
        url: str,
        watchlist_file: Optional[Path] = None,   # <-- new
    ) -> int:
        with self.lock:
            self.job_counter += 1
            job = DownloadJob(
                anime=anime,
                episode=episode,
                watchlist=watchlist,
                destination=destination,
                url=url,
                watchlist_file=watchlist_file,
            )
            self.jobs[self.job_counter] = job
            self.queue.append(self.job_counter)
            self._start_workers()
        return self.job_counter

    def _start_workers(self):
        if not self.running:
            self.running = True
            for _ in range(self.max_workers):
                t = threading.Thread(target=self._worker_loop, daemon=True)
                t.start()

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
        logger.info(
            f"⏳ Downloading {job.anime.name} episode {job.episode} (job {job_id})"
        )
        success = download_file(
            job.url,
            job.destination,
            anime_name=job.anime.name,
            episode=job.episode,
        )
        if success:
            job.status = "completed"
            update_watchlist(
                job.watchlist,
                job.anime,
                job.episode,
                file_path=job.watchlist_file,
            )
            remove_success(job.anime.name, job.episode)
            logger.info(f"✅ Job {job_id} completed")
        else:
            job.status = "failed"
            add_failed(job.anime.name, job.episode)
            logger.error(f"❌ Job {job_id} failed")

    def get_status(self):
        with self.lock:
            return {
                jid: (job.status, job.anime.name, job.episode)
                for jid, job in self.jobs.items()
            }