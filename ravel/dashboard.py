import time
from tqdm import tqdm
from .scheduler import queue, running

def dashboard(refresh=0.5):
    """Display the dashboard"""
    bars = {}
    try:
        while True:
            if not queue and not running:
                for bar in bars.values():
                    bar.n = bar.total
                    bar.refresh()
                    bar.close()
                print("All jobs are finished.")
                break

            for job_id, job in running.items():
                if job_id not in bars:
                    bars[job_id] = tqdm(
                        total=100,
                        desc=f"{job_id}",
                        position=len(bars),
                        leave=True
                    )

            for job_id, bar in bars.items():
                if job_id in running and bar.n < 99:
                    bar.update(1)

            finished = set(bars) - set(running)
            for job_id in finished:
                bar = bars.pop(job_id)
                bar.n = 100
                bar.refresh()
                bar.close()
                print(f"{job_id} finished")

            time.sleep(refresh)

    except KeyboardInterrupt:
        for bar in bars.values():
            bar.close()