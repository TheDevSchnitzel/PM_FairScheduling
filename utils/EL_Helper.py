import math 
import utils.extractor as extractor
import utils.frames as frames

def GetSegments(log):
    segments = []
    
    for trace in log:
        n = len(trace)        
        lastAct = 'None'
        
        for i in range(n):
            event = trace[i]
            nextAct = event['concept:name']
                
            if (lastAct, nextAct) not in segments:                
                segments.append((lastAct, nextAct))
                
            lastAct = nextAct
    return segments

def GetActivities(log):
    activities = []
    
    for trace in log:
        n = len(trace)        
        
        for i in range(n):
            event = trace[i]
            if event['concept:name'] not in activities:
                activities.append(event['concept:name'])
    return sorted(['None'] + activities)


def GetWindows(log, wndNumberCallback = None):
    no_events = sum([len(trace) for trace in log])
    
    if wndNumberCallback is None:
        windowNumber = 1 * math.ceil(math.sqrt(no_events))
    else:
        windowNumber = wndNumberCallback(no_events)
    
    # Convert XES-Events into dict {'act', 'ts', 'res', 'single', 'cid'}
    event_dict = extractor.event_dict(log, res_info=True)
    windowWidth = frames.get_width_from_number(event_dict, windowNumber)
    return frames.bucket_window_dict_by_width(event_dict, windowWidth)