"""Local stdio MCP bridge. No listening network port, no credential handling."""
import json,sys,subprocess,os,time,ctypes,threading
from pathlib import Path
from limits import LimitsClient,windows_from_limits
sys.stdout.reconfigure(encoding='utf-8')
sys.stdin.reconfigure(encoding='utf-8')
BASE=Path(__file__).resolve().parent
STATE=Path(os.environ.get('QUOTA_WIDGET_STATE',str(Path(os.environ.get('LOCALAPPDATA',str(BASE)))/'QuietQuota')))
STATE.mkdir(parents=True,exist_ok=True)

def status():
    try:return json.loads((STATE/'status.json').read_text('utf-8'))
    except (OSError,ValueError):return {}

def alive():
    pid=status().get('pid')
    if not pid:return False
    k=ctypes.windll.kernel32;k.OpenProcess.restype=ctypes.c_void_p
    h=k.OpenProcess(0x1000,False,int(pid))
    if not h:return False
    code=ctypes.c_ulong();k.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)];k.GetExitCodeProcess(h,ctypes.byref(code));k.CloseHandle.argtypes=[ctypes.c_void_p];k.CloseHandle(h)
    return code.value==259

def start():
    if alive():return {'running':True,'status':status()}
    exe=Path(sys.executable).with_name('pythonw.exe')
    subprocess.Popen([str(exe),str(BASE/'widget.py')],cwd=BASE,env={**os.environ,'QUOTA_WIDGET_STATE':str(STATE)},creationflags=0x08000000,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return {'starting':True}

def command(action):
    if not alive():
        if action=='quit':return {'running':False}
        start()
    path=STATE/'command.json';tmp=STATE/'command.tmp';tmp.write_text(json.dumps({'action':action}),'utf-8');tmp.replace(path)
    return {'requested':action}

TOOLS=[('quota_read','读取当前登录账户的 Codex 额度，不是 ChatGPT 模型消息额度',True),('widget_start','启动余量悬浮组件',False),('widget_settings','打开余量设置',False),('widget_refresh','刷新组件的 Codex 额度',False),('widget_stop','退出余量悬浮组件',False)]
def run(method,params):
    if method=='initialize':return {'protocolVersion':params.get('protocolVersion','2024-11-05'),'capabilities':{'tools':{}},'serverInfo':{'name':'quiet-quota','version':'1.0.0'}}
    if method=='ping':return {}
    if method=='tools/list':return {'tools':[{'name':n,'description':d,'inputSchema':{'type':'object','properties':{},'additionalProperties':False},'annotations':{'readOnlyHint':r,'destructiveHint':False,'openWorldHint':n=='quota_read'}} for n,d,r in TOOLS]}
    if method=='tools/call':
        n=params['name']
        try:
            if n=='quota_read':value={'source':'Codex','updated':time.time(),'windows':windows_from_limits(LimitsClient().read())}
            elif n=='widget_start':value=start()
            elif n=='widget_settings':value=command('settings')
            elif n=='widget_refresh':value=command('refresh')
            elif n=='widget_stop':value=command('quit')
            else:raise ValueError('Unknown tool')
            return {'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}]}
        except Exception as e:return {'content':[{'type':'text','text':str(e)}],'isError':True}
    raise ValueError('Method not found')
if __name__=='__main__':
    start()
    for line in sys.stdin:
        try:
            req=json.loads(line)
            if 'id' not in req:continue
            result=run(req['method'],req.get('params') or {})
            print(json.dumps({'jsonrpc':'2.0','id':req['id'],'result':result},ensure_ascii=False),flush=True)
        except Exception as e:
            print(json.dumps({'jsonrpc':'2.0','id':req.get('id'),'error':{'code':-32603,'message':str(e)}}),flush=True)
