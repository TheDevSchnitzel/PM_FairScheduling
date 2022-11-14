import pm4py
from pm4py.objects.log.exporter.xes import exporter as xes_exporter
import random



# Take an eventlog and re-assign/map the resources to different ones
# => Create skewed resource distributions

def GetActivityResourceMapping(log):
    actResMapping = {}
    actFreq = {}
    
    for trace in log:
        n = len(trace)
        for i in range(n):
            event = trace[i]
            act = event['concept:name']
            res = event['org:resource']
            #event['org:resource'] = GetResource(act)
            
            if act in actResMapping:
                if res not in actResMapping[act]:
                    actResMapping[act].append(res)
                actFreq[act] += 1
            else:
                actResMapping[act] = [res]
                actFreq[act] = 1
    print(actResMapping)
    print(actFreq)
    
def GetResource(map, act):
    l = map[act]
    
    if len(l[0]) == 1:
        return l[0]
    else:
        return random.choice(l)

def ApplyMapping(log):
    # actResMap = {'reg': [4, 66, 92, 70, 68, 97, 15, 3, 95, 94, 16, 17, 98, 69, 67, 1, 10, 96, 91, 2, 93], 'inv': [67, 96, 15, 10, 92, 93, 68, 3, 1, 16, 17, 66, 2, 98, 91, 95, 4, 70, 69, 94, 97], 'answer': [6, 'Jane', 71, 82, 75, 7, 77, 9, 76, 74, 73, 72, 80, 79, 78, 8, 81], 'report': [6, 'Jane', 71, 82, 75, 7, 77, 9, 76, 74, 73, 72, 80, 79, 78, 8, 81], 'close': [16, 92, 66, 98, 69, 17, 68, 93, 91, 97, 10, 3, 1, 67, 15, 94, 70, 4, 96, 2, 95], 'Frontline Resolution': [70, 98, 95, 17, 15, 96, 66, 91, 97, 69, 93, 67, 10, 2, 16, 68, 3, 1, 92, 94, 4], 'follow': [4, 67, 97, 68, 17, 93, 91, 2, 95, 70, 16, 10, 92, 94, 15, 1, 3, 69, 96, 66, 98]}
    actResMap = {
        'reg':                  (['System'], [1]), 
        'inv':                  (['R1', 'R2', 'R3'], [0.5, 0.4, 0.1]), 
        'answer':               (['R1', 'R4', 'R5'], [0.5, 0.4, 0.1]), 
        'report':               (['R1', 'R2', 'R4'], [0.5, 0.4, 0.1]), 
        'Frontline Resolution': (['R5'], [1]), 
        'follow':               (['R1', 'R2', 'R3'], [0.5, 0.4, 0.1]), 
        'close':                (['System'], [1])
    }
    
    actResMapDist = { }
    for act, (res, p) in actResMap.items():
        if len(res) == 1:
            actResMapDist[act] = res
        else:
            actResMapDist[act] = [res[i] * (p[i]*100) for i in range(len(res))]
    
    for trace in log:
        n = len(trace)
        for i in range(n):
            event = trace[i]
            event['org:resource'] = GetResource(actResMapDist, event['concept:name'])
    return log
    
def main():
    log = pm4py.read_xes("../logs/log.xes")

    #GetActivityResourceMapping(log)
    log = ApplyMapping(log)
    xes_exporter.apply(log, '../logs/log_ResReduced.xes')


if __name__ == '__main__':
    main()