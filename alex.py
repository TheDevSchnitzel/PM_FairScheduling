import pandas as pd
import matplotlib.pyplot as plt
import datetime
import math

def GetResourceLoadDistribution(activity_set, resource_set, segment_set, event_dic, trig_dic, bucket_window_dic, id_frame_mapping, id_pairs, res_info, act_selected, res_selected):
    frames = sorted(bucket_window_dic.keys())

    # Events/Res/Window
    resLoad = {frame: {str(r): 0 for r in resource_set} for frame in frames}
    for e in event_dic.keys():
        # get frame id for this event
        frame_id = id_frame_mapping[e]   
        (frameStart, frameEnd) = bucket_window_dic[frame_id]
        event = event_dic[e]
    
        if str(event['res']) not in resLoad[0].keys():
            print('alert, unknown resource ' + str(event['res']))
        # Increase the resource counter
        resLoad[frame_id][str(event['res'])] += 1
    
    df = pd.DataFrame.from_dict(resLoad, orient='index')
    df.to_csv('resLoad.csv')
    
    del df
    del resLoad
    
    
    
    
def GetResourceTimeDistribution(resource_set, event_dic, bucket_window_dic, id_frame_mapping, id_pairs, trig_dic):
    frames = sorted(bucket_window_dic.keys())

    resLoad = {frame: {str(r): 0 for r in resource_set} for frame in frames}
    
    singles = [i for i in event_dic.keys() if event_dic[i]['single'] or len(trig_dic[i]) == 0]
    
    # Time/Res/Window
    for event_id in singles:
        # get frame id for this event
        frame_id = id_frame_mapping[event_id]        
        (frameStart, frameEnd) = bucket_window_dic[frame_id]        
        event = event_dic[event_id]        
        resLoad[frame_id][str(event['res'])] += frameEnd - event['ts']
        
    for (i_event_id, j_event_id) in id_pairs:
        # get frame id for this event
        i_frame_id = id_frame_mapping[i_event_id]
        j_frame_id = id_frame_mapping[j_event_id]
        
        (i_frameStart, i_frameEnd) = bucket_window_dic[i_frame_id]
        (j_frameStart, j_frameEnd) = bucket_window_dic[j_frame_id]
        
        i_event = event_dic[i_event_id]
        j_event = event_dic[j_event_id]
    
        if i_frame_id == j_frame_id:
            resLoad[i_frame_id][str(i_event['res'])] += j_event['ts'] - i_event['ts']
            resLoad[j_frame_id][str(j_event['res'])] += j_frameEnd - j_event['ts']
        else:
            resLoad[i_frame_id][str(i_event['res'])] += i_frameEnd - i_event['ts']
            resLoad[j_frame_id][str(j_event['res'])] += j_frameEnd - j_event['ts']
        
    df = pd.DataFrame.from_dict(resLoad, orient='index')
    df.to_csv('resLoadTime.csv')
    
    del df
    del resLoad
    
  