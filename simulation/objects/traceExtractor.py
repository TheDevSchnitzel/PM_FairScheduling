import pm4py
import utils.extractor as extractor
from simulation.objects.traceInstance import Trace
from simulation.objects.enums import TimestampModes

def ExtractTraces(log, timestampMode, timestampAttribute):
    if type(log) == str:
        log = pm4py.read_xes(log)

    events = extractor.event_dict(log, res_info=True)
    eventTraces = {cid:[] for cid in set([e['cid'] for _, e in events.items()])}
    traces = []

    # Build the event traces
    for _, e in events.items():
        eventTraces[e['cid']].append(e)            
    
    # Sort events in traces by timestamp
    for cid in eventTraces.keys():
        if timestampMode == TimestampModes.START or timestampMode == TimestampModes.END:
            eventTraces[cid].sort(key=lambda e: e[timestampAttribute])
            traces.append(Trace(str(cid), [(e['act'], e['res'], e[timestampAttribute]) for e in eventTraces[cid]]))
        else:
            eventTraces[cid].sort(key=lambda e: e[timestampAttribute[0]])
            traces.append(Trace(str(cid), [(e['act'], e['res'], e[timestampAttribute[0]], e[timestampAttribute[1]]) for e in eventTraces[cid]]))
    
    return traces
    
def ExtractActivityResourceMapping(traces):
    """ Get the mapping between Resources and Activities in order """
    AtoR = {}
    RtoA = {}
    
    for trace in traces:
        for e in trace.future:
            act = e[0]
            res = e[1]

            if act not in AtoR:
                AtoR[act] = []                
            if res not in RtoA:
                RtoA[res] = []
            
            if res not in AtoR[act]:
                AtoR[act].append(res)            
            if act not in RtoA[res]:
                RtoA[res].append(act)
    
    return {a: sorted(AtoR[a]) for a in AtoR}, {r: sorted(RtoA[r]) for r in RtoA}, sorted([a for a in AtoR.keys()]), sorted([r for r in RtoA.keys()])