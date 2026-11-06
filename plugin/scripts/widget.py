"""余量: Windows native companion, no third party Python dependencies."""
import ctypes as C
from ctypes import wintypes as W
import tkinter as tk
from tkinter import ttk, colorchooser
import json, time, threading, queue, os, sys
from pathlib import Path
from datetime import datetime
from limits import LimitsClient, windows_from_limits

BASE=Path(__file__).resolve().parent
STATE=Path(os.environ.get('QUOTA_WIDGET_STATE',str(Path(os.environ.get('LOCALAPPDATA',str(BASE)))/'QuietQuota')))
STATE.mkdir(parents=True,exist_ok=True)
PREF=STATE/'preferences.json'
PALETTES={'雨后鼠尾草':('#f6faf7','#83ac96','#334b40','#5c7266','#e2eae4'),'天青米杏':('#faf7f0','#8dbdce','#354953','#60727a','#e5e9e7'),'蜜桃燕麦':('#fcf7f3','#c8a093','#59443f','#7b655d','#eee3dd'),'海盐薄荷':('#f3f9f9','#7eaeae','#324d50','#5a7375','#dfebea'),'奶油麦田':('#fbf9f1','#b8ae7e','#514e38','#716e56','#ece8d9'),'静夜石墨':('#292d2d','#9abbb0','#e6eeea','#afc0b9','#424e49')}
u=C.windll.user32;k=C.windll.kernel32
u.GetForegroundWindow.restype=W.HWND
u.GetWindowLongPtrW.argtypes=[W.HWND,C.c_int];u.GetWindowLongPtrW.restype=C.c_ssize_t
u.SetWindowLongPtrW.argtypes=[W.HWND,C.c_int,C.c_ssize_t]
u.SetWindowPos.argtypes=[W.HWND,W.HWND,C.c_int,C.c_int,C.c_int,C.c_int,W.UINT]
u.GetAncestor.argtypes=[W.HWND,W.UINT];u.GetAncestor.restype=W.HWND
u.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
u.IsWindowVisible.argtypes=[W.HWND];u.IsIconic.argtypes=[W.HWND]
u.GetWindowRect.argtypes=[W.HWND,C.POINTER(W.RECT)]
k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
k.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)]
k.CloseHandle.argtypes=[W.HANDLE]
try:u.SetProcessDpiAwarenessContext(C.c_void_p(-4))
except Exception:pass

def target_windows():
    found=[]
    @C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    def each(hwnd,param):
        if not u.IsWindowVisible(hwnd):return True
        pid=W.DWORD();u.GetWindowThreadProcessId(hwnd,C.byref(pid))
        if pid.value==os.getpid():return True
        handle=k.OpenProcess(0x1000,False,pid.value)
        if handle:
            buf=C.create_unicode_buffer(2048);size=W.DWORD(2048)
            if k.QueryFullProcessImageNameW(handle,0,buf,C.byref(size)):
                name=Path(buf.value).name.lower()
                if name in ('codex.exe','chatgpt.exe'):
                    r=W.RECT();u.GetWindowRect(hwnd,C.byref(r))
                    if r.right-r.left>180:found.append((hwnd,r,name))
            k.CloseHandle(handle)
        return True
    u.EnumWindows(each,0)
    return found

class App:
    def __init__(self):
        self.p={'palette':'雨后鼠尾草','mode':'follow','side':'right','x':900,'y':180,'offset':0}
        try:self.p.update(json.loads(PREF.read_text('utf-8')))
        except Exception:pass
        self.root=tk.Tk();self.root.withdraw();self.root.title('余量');self.root.overrideredirect(True)
        self.root.geometry(f'224x88+{self.p["x"]}+{self.p["y"]}')
        self.root.update_idletasks();self.hwnd=u.GetAncestor(self.root.winfo_id(),2)
        style=u.GetWindowLongPtrW(self.hwnd,-20);u.SetWindowLongPtrW(self.hwnd,-20,style|0x80)
        try:
            corner=C.c_int(2);C.windll.dwmapi.DwmSetWindowAttribute(W.HWND(self.hwnd),33,C.byref(corner),4)
        except Exception:pass
        self.canvas=tk.Canvas(self.root,width=224,height=88,highlightthickness=0);self.canvas.pack()
        self.canvas.bind('<Button-1>',self.click);self.canvas.bind('<B1-Motion>',self.drag);self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<Button-3>',lambda e:self.settings());self.canvas.bind('<Enter>',lambda e:self.hover(True));self.canvas.bind('<Leave>',lambda e:self.hover(False))
        self.root.bind('<Escape>',lambda e:self.close_pop())
        self.windows={300:None,10080:None};self.updated=0;self.error='正在读取';self.busy=False;self.events=queue.Queue();self.client=LimitsClient();self.pop=None;self.setting=None;self.hovered=False;self.drag_start=None;self.target=None;self.visible=False;self.next_refresh=0;self.stopping=False
        self.root.protocol('WM_DELETE_WINDOW',self.quit)
        self.draw();self.refresh();self.tick();self.root.mainloop()
    def palette(self):
        values=list(PALETTES.get(self.p.get('palette'),PALETTES['雨后鼠尾草']))
        if self.p.get('custom_bg'):values[0]=self.p['custom_bg']
        if self.p.get('custom_accent'):values[1]=self.p['custom_accent']
        return values
    def save(self):
        try:PREF.write_text(json.dumps(self.p,ensure_ascii=False,indent=2),'utf-8')
        except OSError:pass
    def hover(self,v):self.hovered=v;self.draw()
    def countdown(self,x):
        if not x:return '暂不可用'
        if not x.get('reset'):return '重置时间未知'
        n=max(0,int((x['reset']-time.time())/60));d,n=divmod(n,1440);h,m=divmod(n,60)
        return ('即将重置' if x['reset']<=time.time()+60 else (f'{d}天{h}小时' if d else (f'{h}小时' if h else '')+f'{m}分')+'后重置')
    def draw(self):
        bg,accent,ink,muted,track=self.palette();c=self.canvas;c.configure(bg=bg);c.delete('all')
        for i,(duration,label) in enumerate(((300,'5h'),(10080,'7d'))):
            y=11+i*36;x=self.windows[duration]
            c.create_oval(12,y,40,y+28,outline=track,width=3)
            if x and x['remaining']>0:
                pct=x['remaining'];extent=-359.9 if pct>=100 else -pct*3.6
                c.create_arc(12,y,40,y+28,start=90,extent=extent,style='arc',outline=accent,width=3)
                import math
                for a in (90,90+extent):
                    px=26+14*math.cos(math.radians(a));py=y+14-14*math.sin(math.radians(a));c.create_oval(px-1.5,py-1.5,px+1.5,py+1.5,fill=accent,outline='')
            c.create_text(26,y+14,text=label,fill=ink,font=('Segoe UI',9,'bold'))
            c.create_text(53,y+14,anchor='w',text=(f'{x["remaining"]:.0f}%' if x else '—'),fill=ink,font=('Segoe UI',13))
            text='未更新' if self.error and self.updated else self.countdown(x)
            c.create_text(106,y+14,anchor='w',text=text,fill=muted,font=('Microsoft YaHei UI',8))
        c.create_text(215,6,text='⚙',fill=ink if self.hovered else muted,font=('Segoe UI',8))
        if self.error:c.create_oval(3,3,6,6,fill=muted,outline='')
    def click(self,e):
        if e.x>203 and e.y<16:self.settings();return
        if e.y<9 or e.x<8 or e.x>217:
            self.drag_start=(e.x_root,e.y_root,self.root.winfo_x(),self.root.winfo_y());return
        self.details(300 if e.y<45 else 10080)
    def drag(self,e):
        if not self.drag_start:return
        a,b,x,y=self.drag_start;self.root.geometry(f'+{max(0,x+e.x_root-a)}+{max(0,y+e.y_root-b)}')
    def release(self,e):
        if not self.drag_start:return
        self.drag_start=None;self.p['x']=self.root.winfo_x();self.p['y']=self.root.winfo_y()
        if self.target and self.p['mode']=='follow':
            _,r,_=self.target;x,y=self.p['x'],self.p['y'];choices={'right':abs(x-r.right),'left':abs(x+224-r.left),'top':abs(y+88-r.top),'bottom':abs(y-r.bottom)};side=min(choices,key=choices.get)
            if choices[side]<55:
                self.p['side']=side;self.p['offset']=(y-r.top if side in ('left','right') else x-r.left)
            else:self.p['mode']='free'
        self.save()
    def close_pop(self):
        if self.pop:self.pop.destroy();self.pop=None
    def floating(self,title,width,height):
        bg,accent,ink,muted,track=self.palette()
        p=tk.Toplevel(self.root);p.withdraw();p.title(title);p.overrideredirect(True);p.attributes('-topmost',True)
        x=self.root.winfo_x()+224-width;y=self.root.winfo_y()+96
        class PopMonitor(C.Structure):_fields_=[('size',W.DWORD),('monitor',W.RECT),('work',W.RECT),('flags',W.DWORD)]
        u.MonitorFromWindow.argtypes=[W.HWND,W.DWORD];u.MonitorFromWindow.restype=W.HANDLE
        info=PopMonitor();info.size=C.sizeof(info);u.GetMonitorInfoW.argtypes=[W.HANDLE,C.POINTER(PopMonitor)]
        if u.GetMonitorInfoW(u.MonitorFromWindow(self.hwnd,2),C.byref(info)):
            area=info.work;x=max(area.left+8,min(area.right-width-8,x));y=max(area.top+8,min(area.bottom-height-8,y))
        p.geometry(f'{width}x{height}{x:+d}{y:+d}');p.configure(bg=track)
        c=tk.Canvas(p,width=width,height=height,bg=bg,highlightthickness=1,highlightbackground=track);c.pack()
        p.update_idletasks()
        hwnd=u.GetAncestor(p.winfo_id(),2)
        # Give frameless popovers the same rounded silhouette as the web prototype.
        g=C.windll.gdi32;g.CreateRoundRectRgn.argtypes=[C.c_int]*6;g.CreateRoundRectRgn.restype=W.HANDLE
        u.SetWindowRgn.argtypes=[W.HWND,W.HANDLE,W.BOOL]
        region=g.CreateRoundRectRgn(0,0,width+1,height+1,18,18);u.SetWindowRgn(hwnd,region,True)
        p.bind('<Escape>',lambda e:p.destroy());p.deiconify()
        return p,c
    def ui_text(self,c,x,y,text,size=12,color=None,bold=False,anchor='w'):
        return c.create_text(x,y,text=text,fill=color or self.palette()[2],font=('Microsoft YaHei UI',-size,'bold' if bold else 'normal'),anchor=anchor)
    def ui_button(self,c,x,y,width,height,text,command,active=False,dot=None):
        bg,accent,ink,muted,track=self.palette();tag='button'+str(len(c.find_all()))
        fill=track if active else bg
        c.create_polygon(x+7,y,x+width-7,y,x+width,y+7,x+width,y+height-7,x+width-7,y+height,x+7,y+height,x,y+height-7,x,y+7,smooth=True,splinesteps=20,fill=fill,outline=accent if active else track,tags=tag)
        if dot:
            c.create_oval(x+7,y+height/2-3,x+13,y+height/2+3,fill=dot,outline='',tags=tag)
            item=self.ui_text(c,x+18,y+height/2,text,10)
        else:item=self.ui_text(c,x+width/2,y+height/2,text,12,anchor='center')
        c.addtag_withtag(tag,item);c.tag_bind(tag,'<Button-1>',lambda e:command());c.tag_bind(tag,'<Enter>',lambda e:c.configure(cursor='hand2'));c.tag_bind(tag,'<Leave>',lambda e:c.configure(cursor=''))
    def details(self,duration):
        if self.pop and self.pop.winfo_exists() and getattr(self.pop,'duration',None)==duration:self.close_pop();return
        self.close_pop();bg,accent,ink,muted,track=self.palette();height=222 if self.error else 188
        p,c=self.floating('余量 · 重置时间',224,height);self.pop=p;p.duration=duration
        self.ui_text(c,18,24,('5h' if duration==300 else '7d')+' 额度重置时间',13,bold=True)
        self.ui_button(c,188,11,24,24,'×',self.close_pop)
        x=self.windows[duration]
        date=datetime.fromtimestamp(x['reset']).astimezone().strftime('%m月%d日  %H:%M') if x and x.get('reset') else '暂不可用'
        self.ui_text(c,18,61,date,18)
        zone=datetime.now().astimezone().strftime('%z')
        self.ui_text(c,18,87,'本地时间  UTC'+zone[:3]+':'+zone[3:],11,muted)
        self.ui_text(c,18,112,'来源  Codex 当前登录账户',11,muted)
        self.ui_text(c,18,132,'最近更新  '+(datetime.fromtimestamp(self.updated).strftime('%H:%M:%S') if self.updated else '尚未成功'),11,muted)
        if self.error:self.ui_text(c,18,155,'暂未更新，请稍后重试',11,muted)
        def refresh_detail():
            self.refresh();self.close_pop()
        self.ui_button(c,18,height-36,188,25,'刷新额度',refresh_detail)
        p.bind('<FocusOut>',lambda e:self.root.after(150,lambda:self.dismiss_unfocused(p)))
        p.focus_set()
    def dismiss_unfocused(self,p):
        if not p.winfo_exists():return
        focused=p.focus_displayof()
        if focused is None or focused.winfo_toplevel()!=p:
            if self.pop==p:self.close_pop()
    def settings(self):
        if self.setting and self.setting.winfo_exists():self.setting.lift();return
        self.close_pop();s,c=self.floating('余量 · 设置',224,460);self.setting=s
        def render():
            if not s.winfo_exists():return
            bg,accent,ink,muted,track=self.palette();c.configure(bg=bg,highlightbackground=track);c.delete('all')
            self.ui_text(c,18,25,'组件设置',14,bold=True)
            self.ui_button(c,187,12,25,25,'×',s.destroy)
            self.ui_text(c,18,64,'显示方式',12,muted)
            modes=[('follow','跟随'),('always','置顶'),('free','独立')]
            def choose(key,value):
                self.p[key]=value
                if key=='palette':self.p.pop('custom_bg',None);self.p.pop('custom_accent',None)
                self.save();self.draw();render()
            for i,(key,label) in enumerate(modes):self.ui_button(c,18+i*65,82,58,29,label,lambda k=key:choose('mode',k),self.p['mode']==key)
            self.ui_text(c,18,135,'吸附位置',12,muted)
            for i,(key,label) in enumerate([('left','左'),('right','右'),('top','上'),('bottom','下')]):self.ui_button(c,18+i*49,152,41,28,label,lambda k=key:choose('side',k),self.p['side']==key)
            c.create_line(18,199,206,199,fill=track)
            self.ui_text(c,18,219,'治愈配色',12,bold=True)
            for i,(name,values) in enumerate(PALETTES.items()):
                self.ui_button(c,18+(i%2)*98,237+(i//2)*35,90,29,name,lambda n=name:choose('palette',n),self.p['palette']==name and not self.p.get('custom_bg') and not self.p.get('custom_accent'),values[1])
            def custom(key):
                color=colorchooser.askcolor(parent=s,title='选择颜色',initialcolor=bg if key=='custom_bg' else accent)[1]
                if color:self.p[key]=color;self.save();self.draw();render()
            self.ui_button(c,18,349,90,28,'自定义底色',lambda:custom('custom_bg'))
            self.ui_button(c,116,349,90,28,'自定义额度环',lambda:custom('custom_accent'))
            self.ui_text(c,18,394,'选择自动保存 · 仅调整小组件',10,muted)
            self.ui_button(c,18,416,90,28,'刷新额度',self.refresh)
            self.ui_button(c,116,416,90,28,'退出组件',self.quit)
        render();s.focus_set()
    def refresh(self):
        if self.busy:return
        self.busy=True;self.next_refresh=time.time()+60
        def worker():
            try:self.events.put(('data',windows_from_limits(self.client.read())))
            except Exception as e:self.events.put(('error',str(e)))
        threading.Thread(target=worker,daemon=True).start()
    def tick(self):
        if self.stopping:return
        command=STATE/'command.json'
        if command.exists():
            try:
                action=json.loads(command.read_text('utf-8')).get('action');command.unlink()
                if action=='show':
                    self.reveal_until=time.time()+120
                    self.root.geometry('+80+120');self.root.deiconify();self.root.lift();self.root.focus_force()
                elif action=='settings':self.settings()
                elif action=='refresh':self.refresh()
                elif action=='quit':self.quit();return
            except (OSError,ValueError):pass
        while not self.events.empty():
            kind,data=self.events.get();self.busy=False
            if kind=='data':self.windows=data;self.updated=time.time();self.error=''
            else:self.error=data
        candidates=target_windows();fg=u.GetForegroundWindow()
        if candidates:self.target=next((v for v in candidates if v[0]==fg),next((v for v in candidates if self.target and v[0]==self.target[0]),candidates[0]))
        else:self.target=None
        host_available=bool(self.target and not u.IsIconic(self.target[0]))
        if not host_available:
            self.close_pop()
            if self.setting and self.setting.winfo_exists():self.setting.destroy();self.setting=None
        mode=self.p['mode'];show=host_available if mode=='follow' else True
        if show:
            if not self.visible:self.root.deiconify();self.visible=True;self.refresh()
            if not self.drag_start:
                if mode=='follow' and self.target and time.time()>=getattr(self,'reveal_until',0):
                    _,r,_=self.target;side=self.p['side'];offset=self.p.get('offset',0);x=r.right+8 if side=='right' else r.left-232 if side=='left' else r.left+offset;y=r.top+offset if side in ('left','right') else r.top-96 if side=='top' else r.bottom+8
                    # Clamp to the host monitor work area, including negative monitor coordinates.
                    class MI(C.Structure):_fields_=[('cbSize',W.DWORD),('monitor',W.RECT),('work',W.RECT),('flags',W.DWORD)]
                    u.MonitorFromWindow.argtypes=[W.HWND,W.DWORD];u.MonitorFromWindow.restype=W.HANDLE
                    info=MI();info.cbSize=C.sizeof(info);monitor=u.MonitorFromWindow(self.target[0],2);u.GetMonitorInfoW.argtypes=[W.HANDLE,C.POINTER(MI)];u.GetMonitorInfoW(monitor,C.byref(info));a=info.work
                    if side=='right' and x+224>a.right:x=r.left-232
                    if side=='left' and x<a.left:x=r.right+8
                    x=max(a.left,min(a.right-224,x));y=max(a.top,min(a.bottom-88,y));self.root.geometry(f'224x88{x:+d}{y:+d}')
                top=time.time()<getattr(self,'reveal_until',0) or mode=='always' or (mode=='follow' and self.target and (fg==self.target[0] or fg==self.hwnd))
                u.SetWindowPos(self.hwnd,W.HWND(-1 if top else -2),0,0,0,0,0x13)
        elif self.visible:
            self.root.withdraw();self.visible=False;self.close_pop()
            if self.setting and self.setting.winfo_exists():self.setting.destroy();self.setting=None
        if self.visible and time.time()>=self.next_refresh:self.refresh()
        status={'pid':os.getpid(),'hwnd':int(self.hwnd),'settingsHwnd':int(u.GetAncestor(self.setting.winfo_id(),2)) if self.setting and self.setting.winfo_exists() else None,'visible':self.visible,'updated':self.updated,'error':self.error,'busy':self.busy,'windows':self.windows,'source':'Codex','target':self.target[2] if self.target else None}
        try:(STATE/'status.json').write_text(json.dumps(status,ensure_ascii=False),'utf-8')
        except OSError:pass
        self.draw();self.root.after(300,self.tick)
    def quit(self):
        self.stopping=True
        if self.client.proc:
            try:self.client.proc.terminate()
            except OSError:pass
        self.root.destroy()

if __name__=='__main__':
    k.CreateMutexW.argtypes=[C.c_void_p,W.BOOL,W.LPCWSTR];k.CreateMutexW.restype=W.HANDLE
    mutex=k.CreateMutexW(None,False,'Local\\QuietQuotaWidget_v1')
    if k.GetLastError()!=183:
        import traceback
        try:App()
        except Exception:
            (STATE/'error.log').write_text(traceback.format_exc(),'utf-8');raise
    else:
        (STATE/'command.json').write_text(json.dumps({'action':'show'}),'utf-8')
