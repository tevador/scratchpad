# (c) 2020 tevador
# Released under the MIT license.

import numpy
import copy

SVC_BOTTOM_CAPACITY=180
SVC_TOP_CAPACITY=3200
CLIENT_PERF=1000
CLIENT_TIMEOUT=30
SMALL_BOTNET_MACHINES=500
LARGE_BOTNET_MACHINES=100000
HS_UPDATE_PERIOD=300
MIN_EFFORT=1000
QUEUE_CAPACITY=CLIENT_TIMEOUT*SVC_BOTTOM_CAPACITY

descriptor_effort=0
handled=[]
backlog=[]
trimmed_count=0
trimmed_list=[]
queue=[]

def increase_effort(effort):
    if effort < MIN_EFFORT:
        return MIN_EFFORT
    return 2 * effort

class Client:
    def __init__(self, time, effort, attacker):
        self.time=time
        self.effort=effort
        self.attacker=attacker
        self.next_time=time

    def reconnect(self, tick):
        self.effort = increase_effort(self.effort)
        next_attempt = self.effort / CLIENT_PERF
        self.next_time = self.next_time + CLIENT_TIMEOUT + next_attempt

def recommend_effort3():
    effort = sum(trimmed_list)
    effort += sum(x.effort for x in handled)
    effort += sum(x.effort for x in queue)
    effort /= SVC_BOTTOM_CAPACITY * HS_UPDATE_PERIOD
    if effort < MIN_EFFORT:
        effort = MIN_EFFORT
    return effort

def recommend_effort2():
    global descriptor_effort
    new_effort = 0
    if trimmed_list:
        new_effort = increase_effort(numpy.amax(trimmed_list))
    if descriptor_effort < new_effort:
        descriptor_effort = new_effort
    else:
        median_handled = 99999999
        if handled:
             median_handled = numpy.median(list(x.effort for x in handled))
        if descriptor_effort > median_handled:
            descriptor_effort = median_handled
        # print 'Median handled: ', median_handled
    if descriptor_effort > 0 and descriptor_effort < MIN_EFFORT:
        descriptor_effort = MIN_EFFORT
    return descriptor_effort

def recommend_effort1():
    global descriptor_effort
    median_trimmed = 0
    if trimmed_list:
        median_trimmed = numpy.median(trimmed_list)
    # print 'Median trimmed: ', median_trimmed
    if descriptor_effort < median_trimmed:
        descriptor_effort = median_trimmed
    else:
        median_handled = 99999999
        if handled:
             median_handled = numpy.median(list(x.effort for x in handled))
        if descriptor_effort > median_handled:
            descriptor_effort = median_handled
        # print 'Median handled: ', median_handled
    if descriptor_effort > 0 and descriptor_effort < MIN_EFFORT:
        descriptor_effort = MIN_EFFORT
    return descriptor_effort

def trim_client(client, time):
    trimmed_list.append(client.effort)
    if not client.attacker:
        clone = copy.copy(client)
        clone.reconnect(tick)
        # print 'Added client to backlog (t = {}, e = {})'.format(clone.next_time, clone.effort)
        backlog.append(clone)

def queue_add(client, tick):
    queue.append(client)

def trim_queue(tick):
    global queue, trimmed_count, QUEUE_CAPACITY
    queue.sort(key=lambda x:x.effort if x.next_time + CLIENT_TIMEOUT >= tick else 0,reverse=True)
    for client in queue[QUEUE_CAPACITY:]:
        trimmed_count = trimmed_count + 1
        # print 'Dropped effort: {0}'.format(client.effort)
        trim_client(client, tick)
    queue = queue[0:QUEUE_CAPACITY]

def get_client_count(tick):
    return 20

class AttStratSustained:
    def __init__(self, machines, start, end):
        self.machines=machines
        self.start=start
        self.end=end

    def get_effort(self, tick):
        global descriptor_effort
        return descriptor_effort + 1 if descriptor_effort > 0 else 0

    def get_count(self, tick):
        machines_now = 0
        if tick >= self.start:
            machines_now = self.machines
        if tick > self.end:
            machines_now = 0
        if machines_now == 0:
            return 0
        return min(SVC_TOP_CAPACITY, int(machines_now * CLIENT_PERF / max(self.get_effort(tick), 1)))

class AttStratPrecomputed(AttStratSustained):
    def __init__(self, machines, start, end):
        self.machines=machines
        self.duration=end-start-HS_UPDATE_PERIOD
        self.start=end-HS_UPDATE_PERIOD
        self.end=end

    def get_effort(self, tick):
        effort = self.duration * self.machines * CLIENT_PERF
        effort /= (SVC_BOTTOM_CAPACITY * HS_UPDATE_PERIOD)
        return effort

    def get_count(self, tick):
        count = 0
        if tick >= self.start:
            count = SVC_BOTTOM_CAPACITY
        if tick > self.end:
            count = 0
        return count

attack_strat = AttStratSustained(LARGE_BOTNET_MACHINES, 150, 7350)

for tick in range(9000):
    effort_sum = 0
    conn_count = 0
    # update descriptor
    if tick % HS_UPDATE_PERIOD == 0:
        descriptor_effort=recommend_effort3()
        # print '(t={}) suggested effort: {}'.format(tick, descriptor_effort)
        total = len(handled)
        legitimate = sum(1 for x in handled if not x.attacker)
        # print 'Total requests: {}, legitimate: {}'.format(total, legitimate)
        # print 'Backlog: {}, Dropped: {}'.format(len(backlog), trimmed_count)
        handled = []
        trimmed_list = []
        trimmed_count = 0
    # handle attacker
    for i in range(attack_strat.get_count(tick)):
        client = Client(tick, attack_strat.get_effort(tick), True)
        queue_add(client, tick)
        effort_sum = effort_sum + client.effort
        conn_count = conn_count + 1
    # handle reconnecting clients
    backlog_count=0
    backlog.sort(key=lambda x:x.next_time)
    for i in range(len(backlog)):
        client = backlog[i]
        # print 'Backlog client: time: {0}, effort: {1}'.format(client.next_time, client.effort)
        if client.next_time > tick:
            break
        queue_add(client, tick)
        effort_sum = effort_sum + client.effort
        conn_count = conn_count + 1
        backlog_count=backlog_count+1
    backlog=backlog[backlog_count:]
    # handle new clients
    for i in range(get_client_count(tick)):
        if descriptor_effort == 0:
            client = Client(tick, descriptor_effort, False)
            queue_add(client, tick)
            effort_sum = effort_sum + client.effort
            conn_count = conn_count + 1
        else:
            client = Client(tick, descriptor_effort, False)
            client.next_time = tick + descriptor_effort / CLIENT_PERF
            backlog.append(client)
    # trim queue
    trim_queue(tick)
    # handle requests in the queue
    handled_count = 0
    handled_legit_count = 0
    conn_time_sum = 0
    queue_size = len(queue)
    while handled_count < SVC_BOTTOM_CAPACITY:
        if not queue:
            break
        client = queue.pop(0)
        if client.next_time + CLIENT_TIMEOUT < tick:
            # print 'WARNING: client expired at {0}'.format(client.next_time + CLIENT_TIMEOUT)
            continue
        handled.append(client)
        handled_count = handled_count + 1
        if not client.attacker:
            handled_legit_count = handled_legit_count + 1
            conn_time_sum = conn_time_sum + (tick - client.time)
    time_to_conn = '?'
    if handled_legit_count > 0:
        time_to_conn = str(conn_time_sum / handled_legit_count)
    #print 't = {:4d}: desc = {:07.1f}, avg = {:07.1f}, queue: {:4d}, backlog: {:4d}, handled = {:3d}, TTC: {}'.format(\
    #    tick, descriptor_effort, effort_sum / conn_count, queue_size, len(backlog), handled_legit_count, time_to_conn)
    print tick, descriptor_effort, queue_size, handled_legit_count, time_to_conn
