import pm4py
from pm4py.objects.log.exporter.xes import exporter as xes_exporter
import random
import itertools
from datetime import datetime, timezone
import pandas as pd
import os

def GetIntTs(datetime_ts):
    # From extractor / Bianka
    if isinstance(datetime_ts, str):
        datetime_ts = datetime.strptime(datetime_ts, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    return (datetime_ts - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds()
            
def GetActivityResourceMapping(log):
    actResFrequency = {}
    actResTime = {}
    resFreq = {}
    resTime = {}
    
    for trace in log:
        n = len(trace)
        for i in range(n):
            event = trace[i]
            act = event['concept:name']
            res = event['org:resource']
            ts  = GetIntTs(event['time:timestamp'])
                        
            if res in resFreq:
                resFreq[res] += 1
            else: 
                resFreq[res] = 1
                resTime[res] = 0
                            
            if act in actResFrequency:
                if res in actResFrequency[act]:
                    actResFrequency[act][res] += 1
                else:
                    actResFrequency[act][res] = 1
                    actResTime[act][res]      = 0
            else:
                actResFrequency[act] = {res: 1}
                actResTime[act]      = {res: 0}
                
            if i > 0:
                prevTS = GetIntTs(trace[i-1]['time:timestamp'])
                duration = ts - prevTS
                actResTime[act][res] += duration
                resTime[res]         += duration
    
    R = list(resFreq.keys())
    R.sort()
    A = list(actResFrequency.keys())
    A.sort()
    sortedAtoR = {a: sorted(list(set([r for r in actResTime[a].keys()]))) for a in A}
    
    
    sumTime = sum([resTime[r] for r in R])
    sumFreq = sum([resFreq[r] for r in R])
    
    df1 = pd.DataFrame(data={
        'Resource': R, 
        'Total-Activities': [resFreq[r] for r in R], 
        'Relative-Activities': [resFreq[r] / sumFreq for r in R],
        'Total-Time': [resTime[r] for r in R], 
        'Relative-Time': [resTime[r] / sumTime for r in R],
    })    
                
    df2 = pd.DataFrame(data={
        'Activity': [a for a in A for _ in range(len(actResTime[a]))], 
        'Resource': [r for a in A for r in sortedAtoR[a]], 
        'Total-Activities': [actResFrequency[a][r] for a in A for r in sortedAtoR[a]], 
        'Relative-Activities': [actResFrequency[a][r] / sumFreq for a in A for r in sortedAtoR[a]],
        'Total-Time': [actResTime[a][r] for a in A for r in sortedAtoR[a]], 
        'Relative-Time': [actResTime[a][r] / sumTime for a in A for r in sortedAtoR[a]],
    })    
    return df1, df2                
                
    
def main(original, processed):
    origLog = pm4py.read_xes(original)

    with pd.ExcelWriter('workDistribution.xlsx') as writer:
        df1, df2 = GetActivityResourceMapping(origLog)
        df1.to_excel(writer, sheet_name='Original_WORK')
        df2.to_excel(writer, sheet_name='Original_TIME')
        del origLog
        
        simData = {'Resource': df1['Resource'], 'ORIG-TIME' : df1['Relative-Time'], 'ORIG-WORK' : df1['Relative-Activities']}
        
        for log in processed:
            fairLog = pm4py.read_xes(log)
            df1, df2 = GetActivityResourceMapping(fairLog)  
            
            fName = os.path.basename(log)
            
            simData[f'{fName}_TIME'] = df1['Relative-Time']
            simData[f'{fName}_WORK'] = df1['Relative-Activities']

            df1.to_excel(writer, sheet_name=f'{fName}_WORK')
            df2.to_excel(writer, sheet_name=f'{fName}_TIME')  
            del fairLog
    
    with pd.ExcelWriter('data.xlsx') as writer:
        df = pd.DataFrame(data=simData)
        df.to_excel(writer, sheet_name=f'Data')
        
if __name__ == '__main__':
    # main('../logs/log_ResReduced.xes', [os.path.join('../logs', f) for f in os.listdir('../logs') if os.path.isfile(os.path.join('../logs', f)) and f not in ['log_ResReduced.xes', 'log.xes']])
    main('../logs/gen_Unfair2.xes', ['../logs/sim_genUnfair_WorkBacklog50.xes'])
        #  ['../logs/simulated_fairness_log_EQUAL_WORK_ALWAYS.xes',
        #   '../logs/simulated_fairness_log_EQUAL_WORK_BACKLOG_500.xes',
        #   '../logs/simulated_fairness_log_EQUAL_WORK_BACKLOG_500_CONSTANTLY_RESSCHEDULED.xes'])