import os
import sys
import glob
import time
import asyncio
import logging

import redis
import fanotify

def main():
    logging.getLogger().setLevel(logging.DEBUG)
    fan_fd = fanotify.Init(fanotify.FAN_CLASS_CONTENT, os.O_RDONLY)
    fanotify.Mark(fan_fd,
                  fanotify.FAN_MARK_ADD | fanotify.FAN_MARK_MOUNT,
                  fanotify.FAN_OPEN | fanotify.FAN_EVENT_ON_CHILD,
                  -1,
                  glob.glob('/lib/ld-linux*')[0])
    loop = asyncio.get_event_loop()
    pool = redis.ConnectionPool(host='localhost', port=6379, db=0)
    redis_connection = redis.Redis(connection_pool=pool)
    loop.add_reader(fan_fd, sync_handle_buf, fan_fd, redis_connection)
    loop.run_forever()

def sync_handle_buf(fan_fd, redis_connection):
    start_time = time.time()
    buf = os.read(fan_fd, 4096)
    assert buf
    while fanotify.EventOk(buf):
        buf, event = fanotify.EventNext(buf)
        if event.mask & fanotify.FAN_Q_OVERFLOW:
            logging.info('queue overflow')
            continue
        fdpath = '/proc/self/fd/{:d}'.format(event.fd)
        target_path = os.readlink(fdpath)
        pid = event.pid
        pid_has_name = redis_connection.hexists('pid_names', pid)
        pid_has_path = redis_connection.hexists('pid_paths', pid)
        if pid_has_name:
            name = redis_connection.hget('pid_names', pid).decode('utf-8')
        else:
            fdpath = '/proc/{:d}/exe'.format(event.pid)
            try:
                name = os.readlink(fdpath)
            except:
                if pid_has_path:
                    first_path = redis_connection.hget('pid_paths', pid).decode('utf-8')
                    name = first_path
                else:
                    redis_connection.hset('pid_paths', pid, target_path)
                    name = target_path
            redis_connection.hset('pid_names', pid, name)
        logging.info('time: {:f} pid: {:d} exe: {:s} opened {:s}, analysis took {:f}'.format(start_time, pid, name, target_path, time.time()-start_time))
        os.close(event.fd)
    assert not buf

if __name__ == '__main__':
    main()
