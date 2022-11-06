from concurrent import futures
import sys
import os
from pathlib import Path
import time

import numpy as np
import math

from .enums import Callbacks,TimestampModes,SimulationModes

class Trace:
    def __init__(self, case, events):
        self.case = case     
        self.history = []      # [(start_ts, end_ts, res, (a,r,ts)) ...]
        self.future = events   # [(a,r,ts) or (a,r,ts_start, ts_end)...]
        self.currentAct = None # (start_ts, exec.res, (a,r,ts))
        self.waiting = True # Not yet started, first event has still to come
        
        
    def IsWaiting(self) -> bool:
        return self.waiting
    
    def HasRunningActivity(self) -> bool:
        return self.currentAct is not None
    
    def HasEnded(self) -> bool:
        return self.currentAct is None and len(self.future) == 0
    
    def NextEventInWindow(self, windowLower, windowUpper) -> bool:
        return len(self.future) > 0 and windowLower <= self.future[0][2] <= windowUpper
    
    def GetNextActivity(self, simMode: SimulationModes) -> str:
        if simMode == SimulationModes.KNOWN_FUTURE:
            return self.future[0][0]
        elif simMode == SimulationModes.PREDICTED_FUTURE:
            raise Exception("TODO: Implement!")
        else:
            raise Exception("Unknown mode for simulation!")
    
    def GetNextEvent(self, simMode: SimulationModes) -> str:
        if simMode == SimulationModes.KNOWN_FUTURE:
            return self.future[0]
        elif simMode == SimulationModes.PREDICTED_FUTURE:
            raise Exception("TODO: Implement!")
        else:
            raise Exception("Unknown mode for simulation!")
        
    def GetRemainingActivityTime(self, mode: TimestampModes,  time: int) -> int:
        if self.currentAct is None:
            return 0
        elif len(self.currentAct[2]) == 3:
            if mode == TimestampModes.END:
                if len(self.history) == 0:
                    #print("TODO: Implement? - Problematic to chose a first timestamp - Naive approach used currently")
                    return self.currentAct[2][2] - time
                else:
                    duration = (self.currentAct[2][2] - self.history[-1][3][2]) # End of current event - End of previous event (Ends are known or predicted)
                    return (self.currentAct[0] + duration) - time # Start time + duration - current time = remaining time
            elif mode == TimestampModes.START:
                if len(self.future) > 0:
                    duration = (self.future[0][1][2] - self.currentAct[2][2]) # Start of next event - Start of current event  (Starts are known or predicted)
                    return (self.currentAct[0] + duration) - time # Start time + duration - current time = remaining time
                else:
                    raise Exception("TODO: Implement!")
                    return "PROBLEM"
        elif len(self.currentAct[2]) == 4:
            duration = (self.currentAct[2][3] - self.currentAct[2][2])
            return (self.currentAct[0] + duration) - time # Start time + duration - current time = remaining time
        else:
            raise Exception("Illegal state!")
    
    def GetNextActivityTime(self) -> int:
        return 0
    
    
    def EndCurrentActivity(self, time):
        if self.currentAct is None:
            raise Exception("Illegal state!")
        
        # Build (start_ts, end_ts, res, (a,r,ts) ... or (a,r,start_ts, end_ts))
        self.history.append((self.currentAct[0], time, self.currentAct[1], self.currentAct[2]))
        self.currentAct = None

        # Determine waiting status
        if len(self.future) > 0:
            self.waiting = True # Somewhere in the process
        else:
            self.waiting = False # All done here
                        
    def StartNextActivity(self, simMode, startTime, resource):
        self.waiting = False
        self.currentAct = (startTime, resource, self.GetNextEvent(simMode))
        del self.future[0]
        

class TraceInstance:
    #prediction 수행 -> predicted_next_act, time
    #prediction을 위한 input vector
    def __init__(self, name, weight, *args, **kwargs):
        if 'act_sequence' in kwargs:
            act_sequence = kwargs['act_sequence']
            self.set_act_sequence(act_sequence)
            #self.next_act = self.seq[0]
        elif 'initial_activity' in kwargs:
            self.next_act = kwargs['initial_activity']
        else:
            raise AttributeError('Either sequence or initial_activity should be given.')

        if 'res_sequence' in kwargs:
            res_sequence = kwargs['res_sequence']
            self.set_res_sequence(res_sequence)

        if 'dur_sequence' in kwargs:
            dur_sequence = kwargs['dur_sequence']
            self.set_dur_sequence(dur_sequence)

        if 'release_time' in kwargs:
            release_time = kwargs['release_time']
            self.set_release_time(release_time)
        else:
            release_time = False

        if 'initial_index' in kwargs:
            self.cur_index = kwargs['initial_index']
            self.first = True
        else:
            self.cur_index = -1

        self.name = name
        self.next_actual_act = self.act_sequence[self.cur_index+1]
        self.next_pred_act = self.act_sequence[self.cur_index+1]
        self.next_actual_ts = release_time
        self.next_pred_ts = release_time
        self.weight=weight
        self.initial_weight = weight
        self.status = True
        self.pred_act_dur_dict = dict()
        self.pred_time_list = list()
        self.cur_act_trace = list()
        self.cur_res_trace = list()
        self.first = True
        #print("ID: {}-{}, Seq: {}, Cur: {}, Released: {}".format(self.name, self.cur_index, self.act_sequence, self.next_actual_act, release_time))

  

    def update_x(self, act_trace, res_trace):
        int_encoded_act = [self.act_char_to_int[act] for act in act_trace]
        int_encoded_res = [self.res_char_to_int[res] for res in res_trace]
        num_act, num_res = len(self.activity_list), len(self.resource_list)
        # one hot encode X
        onehot_encoded_X = list()
        for act_int, res_int in zip(int_encoded_act, int_encoded_res):
            onehot_encoded_act = [0 for _ in range(num_act)]
            onehot_encoded_act[act_int] = 1
            onehot_encoded_res = [0 for _ in range(num_res)]
            onehot_encoded_res[res_int] = 1
            onehot_encoded = onehot_encoded_act + onehot_encoded_res
            onehot_encoded_X.append(onehot_encoded)

        #zero-pad
        while len(onehot_encoded_X) != self.maxlen:
            onehot_encoded_X.insert(0, [0]*(num_act+num_res))
        onehot_encoded_X = np.asarray(onehot_encoded_X)
        return onehot_encoded_X

    def predict_next_act(self, queue, context= True, ):
        time1 = time.time()
        """
        if self.cur_index > 0:
            act_trace = self.act_sequence[:self.cur_index-1] + [cur_act]
            res_trace = self.res_sequence[:self.cur_index-1] + [resource]
        else:
            act_trace = [cur_act]
            res_trace = [resource]
        """
        X = self.update_x(self.cur_act_trace, self.cur_res_trace)
        if context==True:
            context_X = np.array(list(queue.values()))
            pred_vector, conf_vector = self.model_next_act.predict(X, context_X)
        else:
            pred_vector, conf_vector = self.model_next_act.predict(X, context=False)
        #pred_vector, conf_vector = self.model_next_act.predict(X, context=False)
        pred_index = np.argmax(pred_vector,axis=1)[0]
        pred_next_act = self.act_int_to_char[pred_index]
        conf = conf_vector[pred_index]

        time2 = time.time()
        self.pred_time_list.append(time2-time1)
        return pred_next_act, conf

    def estimate_next_time(self, queue, context= True, pred_act=False, resource=False):
        """
        if self.cur_index > 0:
            act_trace = self.act_sequence[:self.cur_index-1] + [cur_act]
            res_trace = self.res_sequence[:self.cur_index-1] + [resource]
        else:
            act_trace = [cur_act]
            res_trace = [resource]
        """
        if pred_act!= False and resource!=False:
            X = self.update_x(self.cur_act_trace + [pred_act], self.cur_res_trace+ [resource])
        else:
            X = self.update_x(self.cur_act_trace, self.cur_res_trace)
        if context==True:
            context_X = np.array(list(queue.values()))
            dur_pred, conf = self.model_next_time.predict(X, context_X)

        else:
            dur_pred, conf = self.model_next_time.predict(X, context=False)

        pred_dur = math.floor(dur_pred[0][0])
        if pred_dur <= 0:
            pred_dur = 1
        return pred_dur, conf[0]

    def predict_next_time(self, queue, context= True, pred_act=False, resource=False):
        time1 = time.time()
        """
        if self.cur_index > 0:
            act_trace = self.act_sequence[:self.cur_index-1] + [cur_act]
            res_trace = self.res_sequence[:self.cur_index-1] + [resource]
        else:
            act_trace = [cur_act]
            res_trace = [resource]
        """
        if pred_act!= False and resource!=False:
            X = self.update_x(self.cur_act_trace + [pred_act], self.cur_res_trace+ [resource])
        else:
            X = self.update_x(self.cur_act_trace, self.cur_res_trace)
        if context==True:
            context_X = np.array(list(queue.values()))
            dur_pred, conf = self.model_next_time.predict(X, context_X)

        else:
            dur_pred, conf = self.model_next_time.predict(X, context=False)

        pred_dur = math.floor(dur_pred[0][0])
        if pred_dur <= 0:
            pred_dur = 1
        time2 = time.time()
        self.pred_time_list.append(time2-time1)
        return pred_dur, conf[0]

    def update_res_history(self, resource):
        self.res_sequence.append(resource)

    def get_cur_actual_act(self):
        if self.first == True:
            return False
        else:
            return self.cur_actual_act



    def get_next_ts_uncertainty(self, res):
        return self.pred_act_dur_dict[res][1]



    def get_pred_act_dur(self, res):
        try:
            return self.pred_act_dur_dict[res][0]
        except KeyError:
            print("ERROR: {} is not in the dict".format(res.get_name()))
            return 5


  

    def set_next_actual_act(self):
        if self.cur_index < len(self.act_sequence)-1:
            self.next_actual_act = self.act_sequence[self.cur_index+1]

  

    def set_pred_act_dur(self, res, pred_act_dur, conf):
        self.pred_act_dur_dict[res] = [pred_act_dur, conf]



    def clear_pred_act_dur(self):
        self.pred_act_dur_dict = dict()


    def set_next_ts_uncertainty(self, res, next_ts_uncertainty):
        self.pred_act_dur_dict[res][1] = next_ts_uncertainty

  

    def update_actuals(self, t, res, mode, act_res_mat, queue):
        # set next ts
        self.cur_index+=1
        self.first =False
        if self.cur_index > len(self.act_sequence)-1:
            print("{} exceed the limit".format(self.get_name()))
            return
        # set current act
        self.cur_actual_act = self.act_sequence[self.cur_index]

        # set next timestamp
        self.set_next_pred_ts(t+self.get_pred_act_dur(res))
        if mode == 'test':
            self.set_next_actual_ts(t+int(act_res_mat[self.cur_actual_act][res.get_name()]))
        else:
            # (CHANGED)
            self.set_next_actual_ts(self.get_next_pred_ts())
            # next_est_dur, next_time_uncertainty = self.estimate_next_time(queue, context=True, pred_act=self.cur_actual_act, resource=res.get_name())
            # self.set_next_actual_ts(t+next_est_dur)

        # set current seq
        if self.cur_index < len(self.act_sequence)-1:
            self.cur_act_trace = self.act_sequence[:self.cur_index+1]
            self.cur_res_trace = self.res_sequence[:self.cur_index+1]

        # set next act
        if self.cur_index < len(self.act_sequence)-1:
            self.next_actual_act = self.act_sequence[self.cur_index+1]

        self.set_status(False)
        self.update_res_history(res.get_name())
        #print("{}'s {}:Process {} pred_till {} actual_till {}, resource {}, next_act: {},activity_trace: {}, resource_trace: {}".format(self.get_name(), self.cur_index, self.get_cur_actual_act(), self.get_next_pred_ts(),self.get_next_actual_ts(), res.get_name(), self.next_actual_act, self.cur_act_trace, self.cur_res_trace))


    def update_weight(self):
        self.weight += 10000
        return self.weight

    def reset_weight(self):
        self.weight = self.initial_weight


    def check_finished(self, t):
        # index가 sequence length와 같아지면 종
        if self.cur_index >= len(self.act_sequence)-1:
            return True
        else:
            return False

    def set_weighted_comp(self):
        self.weighted_comp = (self.get_next_actual_ts()-self.release_time)*self.initial_weight

