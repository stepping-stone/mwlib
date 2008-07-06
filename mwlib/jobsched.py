"""Simplistic threaded job scheduler"""

import Queue
import threading
import traceback

from mwlib.log import Log

log = Log('mwlib.jobsched')

# ==============================================================================

class JobScheduler(object):
    """Simple threaded job scheduler"""
    
    def __init__(self, num_threads):
        """Init instance with a number of worker threads and a job callable
        
        @param num_threads: number of threads to start
        @type num_threads: int
        """
        
        self.num_threads = num_threads
        self.job_queue = Queue.Queue()
        self.started = False
    
    def add_job(self, job_id, do_job, **kwargs):
        """Schedule a job to be executed in a separate thread. The job_id and
        all additional kwargs are passed to the do_job callable given in the
        constructor.
        
        If called for the first time on this instance, the worker threads will
        be started by this method.
        
        @param job_id: unique ID for this job
        @type job_id: hashable object

        @param do_job: callable which gets called with job_id and kwargs
        @type do_job: callable with signature do_job(job_id, **kwargs) -> None
        """
        
        def worker():
            while True:
                job_id, do_job, kwargs = self.job_queue.get()
                try:
                    if job_id == 'die':
                        break
                    try:                
                        do_job(job_id, **kwargs)
                    except Exception, exc:
                        log.ERROR('Error executing job: %s' % exc)
                        traceback.print_exc()
                finally:
                    self.job_queue.task_done()
        
        if not self.started:
            self.started = True
            for i in range(self.num_threads):
                thread = threading.Thread(target=worker)
                thread.setDaemon(True)
                thread.start()
        
        self.job_queue.put((job_id, do_job, kwargs))
    
    def join(self):
        """Wait for all queued jobs to be finished.
        
        After this method returns, all threads of this scheduler are killed.
        """
        
        if not self.started:
            return
        for i in range(self.num_threads):
            self.job_queue.put(('die', None, None))
        self.job_queue.join()
        self.started = False
    