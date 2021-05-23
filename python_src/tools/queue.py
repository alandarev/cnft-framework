import pika
import time

connection = None
channel = None

last_heartbeat = None

def get_channel():
    global connection
    global channel
    global last_heartbeat

    if not (connection and connection.is_open):
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

    else:
        # Check it is still alive
        # Only if we didn't recently do a check already (because it takes 100ms)
        if not last_heartbeat or last_heartbeat + 20 < time.time():
            last_heartbeat = time.time()
            try:
                connection.process_data_events(time_limit=0.1)
            except Exception:
                connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
                channel = None

    if channel and channel.is_open:
        return channel


    channel = connection.channel()

    channel.queue_declare(queue='doggies', durable=False, exclusive=False, auto_delete=False,
            arguments={
                'x-message-ttl': 29030400000,
                'x-max-priority': 10,
                'expires': 29030400000}) # 1 year time limit

    return channel

def get_channel_info():
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()

    return channel.queue_declare(queue='doggies', durable=False, exclusive=False, auto_delete=False,
            arguments={
                'x-message-ttl': 29030400000,
                'expires': 29030400000}) # 1 year time limit


