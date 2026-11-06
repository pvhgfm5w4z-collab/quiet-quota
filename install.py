"""Install the local plugin and reversible, per-user background listener."""
import json,os,sys,shutil,subprocess,argparse
from pathlib import Path
BASE=Path(__file__).resolve().parent
PLUGIN=BASE/'plugin'
STATE=Path(os.environ.get('LOCALAPPDATA',str(BASE)))/'QuietQuota'

def psquote(s):return "'"+str(s).replace("'","''")+"'"
def run(args):subprocess.run(args,check=True)
def main():
    args=argparse.ArgumentParser();args.add_argument('--uninstall',action='store_true');opt=args.parse_args()
    if sys.platform!='win32':raise SystemExit('Windows only')
    codex=shutil.which('codex')
    if not codex:raise SystemExit('Install Codex CLI and sign in first.')
    STATE.mkdir(parents=True,exist_ok=True)
    link_script="$p=Join-Path ([Environment]::GetFolderPath('Startup')) 'QuietQuota.lnk';"
    if opt.uninstall:
        (STATE/'command.json').write_text('{"action":"quit"}','utf-8')
        run(['powershell','-NoProfile','-Command',link_script+"if(Test-Path -LiteralPath $p){Remove-Item -LiteralPath $p}"])
        run([codex,'plugin','remove','quiet-quota@quiet-quota-local'])
        return
    import tkinter
    pythonw=Path(sys.executable).with_name('pythonw.exe')
    if not pythonw.exists():raise SystemExit('pythonw.exe is required')
    config={'mcpServers':{'quiet_quota':{'command':sys.executable,'args':[str(PLUGIN/'scripts/server.py')],'env':{'QUOTA_WIDGET_STATE':str(STATE)}}}}
    (PLUGIN/'.mcp.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),'utf-8')
    market=BASE/'.agents/plugins';market.mkdir(parents=True,exist_ok=True)
    (market/'marketplace.json').write_text(json.dumps({'name':'quiet-quota-local','plugins':[{'name':'quiet-quota','source':{'source':'local','path':'./plugin'},'policy':{'installation':'AVAILABLE','authentication':'ON_INSTALL'}}]},indent=2),'utf-8')
    run([codex,'plugin','marketplace','add',str(BASE)])
    run([codex,'plugin','add','quiet-quota@quiet-quota-local'])
    script=link_script+"$s=(New-Object -ComObject WScript.Shell).CreateShortcut($p);$s.TargetPath="+psquote(pythonw)+";$s.Arguments="+psquote('"'+str(PLUGIN/'scripts/widget.py')+'"')+";$s.WorkingDirectory="+psquote(PLUGIN/'scripts')+";$s.WindowStyle=7;$s.Save()"
    run(['powershell','-NoProfile','-Command',script])
    subprocess.Popen([str(pythonw),str(PLUGIN/'scripts/widget.py')],creationflags=0x08000000)
    print('Installed. Open a new Codex chat to load Quiet Quota.')
if __name__=='__main__':main()
