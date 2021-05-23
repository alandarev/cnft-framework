from time import sleep

from cli import fill_queue, purge_queue

print("purging queue")
purge_queue()
sleep(1)

print("Filling queue")
fill_queue()
while True:
    sleep(5)
    fill_queue(True)
    print("Heartbeat")
