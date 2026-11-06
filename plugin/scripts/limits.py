import json, subprocess, shutil, threading, queue, time

class LimitsClient:
    def __init__(self):
        self.proc = None
        self.counter = 0
        self.lock = threading.Lock()
    def read(self):
        with self.lock:
            exe = shutil.which('codex')
            if not exe:
                raise RuntimeError('未找到 Codex CLI，请先安装并登录 Codex')
            p = subprocess.Popen([exe,'app-server','--stdio'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8', creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self.proc=p
            q=queue.Queue()
            def reader():
                for line in p.stdout:
                    try: q.put(json.loads(line))
                    except (ValueError,TypeError): pass
                q.put({'eof':True})
            threading.Thread(target=reader,daemon=True).start()
            def send(data):
                p.stdin.write(json.dumps(data)+'\n');p.stdin.flush()
            def wait(id):
                deadline=time.monotonic()+35
                while time.monotonic()<deadline:
                    try: msg=q.get(timeout=max(.1,deadline-time.monotonic()))
                    except queue.Empty: break
                    if msg.get('eof'): raise RuntimeError('Codex 服务已退出')
                    if msg.get('id')==id:
                        if 'error' in msg: raise RuntimeError(msg['error'].get('message','额度读取失败'))
                        return msg['result']
                raise RuntimeError('额度读取超时，稍后重试')
            try:
                send({'id':1,'method':'initialize','params':{'clientInfo':{'name':'quota_widget','version':'1.0.0'},'capabilities':{}}})
                wait(1);send({'method':'initialized'})
                send({'id':2,'method':'account/rateLimits/read'})
                result=wait(2)
                buckets=result.get('rateLimitsByLimitId') or {}
                limits=buckets.get('codex') or result.get('rateLimits')
                if not limits: raise RuntimeError('账户尚未返回额度，请确认 Codex 已登录')
                return limits
            finally:
                p.terminate()
                try:p.wait(timeout=3)
                except subprocess.TimeoutExpired:p.kill()
                self.proc=None

def windows_from_limits(limits):
    result={300:None,10080:None}
    for key in ('primary','secondary'):
        v=limits.get(key)
        if v and v.get('windowDurationMins') in result:
            result[v['windowDurationMins']]={'remaining':max(0,min(100,100-float(v['usedPercent']))),'reset':v.get('resetsAt')}
    return result

if __name__=='__main__':
    try:
        data=LimitsClient().read()
        print(json.dumps({'ok':True,'windows':windows_from_limits(data)},ensure_ascii=False))
    except Exception as e:print(json.dumps({'ok':False,'error':str(e)},ensure_ascii=False))
