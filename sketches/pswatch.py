import psutil
import time
init = set([x for x in psutil.process_iter()])

while True:
    latest = set([x for x in psutil.process_iter()])
    if len(latest-init) > 0:
        for proc in latest-init:
            try:
                print(proc.parent(), 'spawned', proc.exe(), 'at', proc.pid)
            except psutil.NoSuchProcess:
                print('process exited')
        init = latest
    time.sleep(0.001)

