"""Bounded native trial batches; each trial owns its data and integration inputs."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time


def trial_results(engine,actions,settings,cancellation,on_frame,workers,stats):
    lock=threading.Lock();active=0
    def simulate(action,display):
        nonlocal active
        if not settings['checkpoint']():raise InterruptedError('cancelled between physical trials')
        start=time.time()
        with lock:
            active+=1;stats['peak_parallel_trials']=max(stats['peak_parallel_trials'],active)
        try:
            result,evaluation,state=engine.simulate(action,settings|{'cancel_event':cancellation,
                'on_frame':lambda frame:on_frame(frame|{'candidate_index':action['candidate_index']}) if display else None})
            timing={'physics_started_unix_s':start,'physics_completed_unix_s':time.time()}
            return result,evaluation,state,timing
        finally:
            with lock:active-=1
    with ThreadPoolExecutor(max_workers=workers,thread_name_prefix='vivacity-physics-trial') as pool:
        for offset in range(0,len(actions),workers):
            batch=actions[offset:offset+workers]
            futures=[pool.submit(simulate,action,index==0) for index,action in enumerate(batch)]
            # Finish and count the complete batch before adaptive stopping.
            # Consume in candidate order so scheduling cannot change ranking/stopping.
            completed=[future.result() for future in futures]
            for index,(action,values) in enumerate(zip(batch,completed)):
                yield (action,*values,index==len(batch)-1)
