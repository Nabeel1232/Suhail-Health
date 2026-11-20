"""Operational request pacing and fair pending-case ordering.

This module changes no model, prompts, scoring, case truth or spending limits.
No inference response is cached or represented as newly executed work.
"""
from __future__ import annotations
import asyncio,time,json,hashlib
from pathlib import Path
from .common import now

def round_robin(groups:list[list[dict]])->list[dict]:
    return [group[index] for index in range(max((len(g) for g in groups),default=0)) for group in groups if index<len(group)]

def pace_gateway(gateway,interval_seconds=30.0,*,dispatch_log:Path|None=None,clock=time.monotonic,sleep=asyncio.sleep):
    """Pace actual SDK dispatches, including internal finite retries.

    Gateway latency includes this explicit local queue wait. All reservations,
    retry-after handling and immutable call records stay in the gateway.
    """
    if interval_seconds<0:raise ValueError('dispatch interval must be nonnegative')
    if gateway.client is None:return gateway
    original=gateway.client.chat.completions.create
    lock=asyncio.Lock();last=[None]
    async def create(*args,**kwargs):
        async with lock:
            wait=0.0 if last[0] is None else max(0.0,interval_seconds-(clock()-last[0]))
            remaining=wait
            while remaining>0:
                duration=min(25.0,remaining);await sleep(duration);remaining-=duration
            last[0]=clock()
            if dispatch_log is not None:
                with dispatch_log.open('a') as f:f.write(json.dumps({'dispatched_at':now(),'model':kwargs.get('model'),'input_hash':hashlib.sha256(json.dumps(kwargs.get('messages'),ensure_ascii=False).encode()).hexdigest(),'local_wait_seconds':wait,'minimum_dispatch_interval_seconds':interval_seconds})+'\n')
        return await original(*args,**kwargs)
    gateway.client.chat.completions.create=create
    return gateway
