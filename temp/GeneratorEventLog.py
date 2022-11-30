import time
from datetime import datetime, timezone
from pm4py.objects.log.exporter.xes import exporter as xes_exporter
from pm4py.objects.conversion.log import converter as log_converter
import pandas as pd
import random
import numpy as np

def ExportSimulationLog(log, logPath):
    # log = [ (act, res, ts, caseID), ...]
    colCase = []
    colAct = []
    colRes = []
    colTS = []
    
    for trace in log:
        for act, res, ts, case in trace:
            colCase.append(case)
            colAct.append(act)
            colRes.append(res)
            colTS.append(datetime.fromtimestamp(ts, timezone.utc))
                
    
    df = pd.DataFrame(list(zip(colCase, colAct, colTS, colRes)), columns=['case', 'concept:name', 'time:timestamp', 'org:resource'])
    parameters = {log_converter.Variants.TO_EVENT_LOG.value.Parameters.CASE_ID_KEY: 'case'}
    el = log_converter.apply(df, parameters=parameters, variant=log_converter.Variants.TO_EVENT_LOG)

    xes_exporter.apply(el, logPath)
    del log
    del df
    del el

def GenerateEL(traces, variants, actRes, timings, startDate, logPath):
    log = []
    
    for i in range(traces):
        variant = random.choices([v[1] for v in variants], [v[0] for v in variants])[0]
        res = [random.choices(actRes[act][0], actRes[act][1])[0] for act in variant]
        ts  = np.cumsum([timings[act]() for act in variant]) + startDate()
        log.append(list(zip(variant, res, ts, [i]*len(ts))))
    
    ExportSimulationLog(log, logPath)
    
def main():
    # Unfair - CFG
    variants = [
        (0.9, ['Start', 'A', 'B', 'End']), 
        (0.1, ['Start','C','End'])
    ]
    actRes = {
        'Start': (['System'], [1]),
        'End':   (['System'], [1]),
        
        'A': (['R1'], [1]),
        'B': (['R2', 'R3'], [0.9, 0.1]),
        'C': (['R3'], [1])
    }    
    timings = {
        'Start': lambda:1,
        'End':   lambda:1,
        'A': lambda:random.normalvariate(mu=1200, sigma=50),
        'B': lambda:random.normalvariate(mu=900, sigma=50),
        'C': lambda:random.normalvariate(mu=1300, sigma=50),
    }
     
    
    # # Congestion - CFG
    # variants = [
    #     (0.5, ['Start', 'A', 'End']), 
    #     (0.5, ['Start', 'B', 'End'])
    # ]
    # actRes = {
    #     'Start': (['System'], [1]),
    #     'End':   (['System'], [1]),
        
    #     'A': (['R1'], [1]),
    #     'B': (['R1'], [1])
    # }    
    # timings = {
    #     'Start': lambda:1,
    #     'End':   lambda:1,
    #     'A': lambda:random.normalvariate(mu=1200, sigma=50),
    #     'B': lambda:random.normalvariate(mu=900, sigma=50)
    # }
    
    startDateInt = datetime.strptime('2019-11-23 14:51:37', '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    startDateInt = (startDateInt - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds()
    startDate = lambda: random.uniform(startDateInt, startDateInt + 800000000)
    
    # Check that variant-probability sums up to 1
    assert sum([v[0] for v in variants]) == 1
    
    # Check that Resource Distribution sums up to 1
    assert all([sum(v[1]) == 1 for v in actRes.values()])
    
    GenerateEL(10000, variants, actRes, timings, startDate, '../logs/gen_Unfair2.xes')

if __name__ == '__main__':
    main()