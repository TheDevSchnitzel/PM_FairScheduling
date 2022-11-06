import pandas as pd
import utils.extractor as extractor
import utils.component as component
import utils.frames as frames
import matplotlib.pyplot as plt
import datetime

def WindowBorders(log, no_windows):
    event_dict = extractor.event_dict(log, res_info=True)
    
    #Computing frames, partitioning events into frames
    width = frames.get_width_from_number(event_dict, no_windows)
    bucketId_borders_dict = frames.bucket_window_dict_by_width(event_dict, width)
    bucketId_eventList_dict, id_frame_mapping = frames.bucket_id_list_dict_by_width(event_dict, width)
    
    # Good to look after an equal distribution
    eventsPerWindow = [len(bucketId_eventList_dict[x]) for x in bucketId_eventList_dict.keys()]
    
    # Plot events over time
    data = [[datetime.datetime(1900, 1, 1, 0, 3, 12), 1], [datetime.datetime(1900, 1, 1, 0, 3, 13), 3], [datetime.datetime(1900, 1, 1, 0, 3, 14), 10],[datetime.datetime(1900, 1, 1, 0, 3, 20), 5]]
    data = pd.DataFrame({'Date': [datetime.datetime.fromtimestamp(int(event_dict[x]['ts'])) for x in event_dict.keys()]})
    data = data.groupby(data['Date']).size().reset_index(name='Count')
    print(data)
    #plt.plot([x[0] for x in data], [x[1] for x in data])
    plt.plot(data['Date'], data['Count'])
   
    #print(bucketId_borders_dict)
    #datetime.datetime.fromtimestamp(1284286794)
    
    # Plot window borders
    print(no_windows)
    for key in bucketId_borders_dict.keys():
        (_, right) = bucketId_borders_dict[key]
        plt.axvline(x=datetime.datetime.fromtimestamp(right), ymin=0.25, ymax=10, color='red')
        
    plt.show()
    
    