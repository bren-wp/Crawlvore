"""Compatibility facade and cancellable registry synchronization state."""
import threading
import time
from company_fields import COLS, FIELDS, ENTITY_KINDS, norm, formula_safe
from company_store import Store

__all__ = ['COLS', 'FIELDS', 'ENTITY_KINDS', 'norm', 'formula_safe', 'Store', 'UA', 'Stopped', 'Collector']
UA = 'Crawlvora/8.1.7 (local Court Registry directory)'

class Stopped(Exception): pass

class Collector:
    def __init__(self,store):
        self.store=store; self.lock=threading.Lock(); self.stop_event=threading.Event(); self.state={'status':'idle','page':0,'last':0,'processed':0,'added':0,'skipped':0,'errors':0,'logs':[]}; self.last_request=0
    def snapshot(self):
        with self.lock: return dict(self.state,logs=list(self.state['logs']))
    def update(self,**kw):
        with self.lock: self.state.update(kw)
    def log(self,s):
        with self.lock: self.state['logs']=(self.state['logs']+[time.strftime('%H:%M:%S')+'  '+s])[-100:]
    def inc(self,k):
        with self.lock: self.state[k]+=1
    def stop(self):
        with self.lock:
            if self.state['status']=='running': self.state['status']='stopping'; self.stop_event.set()
    def wait(self,n):
        if self.stop_event.wait(max(0,n)): raise Stopped()
