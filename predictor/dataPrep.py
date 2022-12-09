import pm4py
import numpy as np
from itertools import chain
import sys
import os
from pathlib import Path
from simulation.objects.traceExtractor import ExtractTraces, ExtractActivityResourceMapping
from utils.activityDuration import EventDurationsByMinPossibleTime

class TracePredictionData:
    def __init__(self, currentActivity, currentResource, historicActResTuples , nextActivity , currentActivityDuration):
        self.CurrentActivity = currentActivity
        self.CurrentResource = currentResource
        self.HistoricActResTuples = historicActResTuples

        # Prediction targets
        self.NextActivity = nextActivity
        self.CurrentActivityDuration = currentActivityDuration

def PrepareEventlogForActivityPrediction(path, timestampMode, timestampAttribute):
    traces = ExtractTraces(path, timestampMode, timestampAttribute)
    AtoR, RtoA, A, R = ExtractActivityResourceMapping(traces)
    oneHotMap_A, oneHotMap_R = CreateOneHotEncoding(A,R)
    EventDurationsByMinPossibleTime(R, traces)

    return list(chain.from_iterable([PrepareTraceForActivityPrediction(trace, oneHotMap_A, oneHotMap_R) for trace in traces])), oneHotMap_A, oneHotMap_R

def CreateOneHotEncoding(A, R):
    oneHot_A = {a: np.zeros(len(A)) for a in A}
    oneHot_R = {r: np.zeros(len(R)) for r in R}

    for i in range(0, len(A)):
        oneHot_A[A[i]][i] = 1

    for i in range(0, len(R)):
        oneHot_R[R[i]][i] = 1
    
    return oneHot_A, oneHot_R

def PrepareTraceForActivityPrediction(trace, oneHotMap_A, oneHotMap_R):
    data = []
    tracePredData = []

    for i in range(len(trace.future)):
        event = trace.future[i]
        act = event[0]
        res = event[1]

        if len(data) == 0:
            data.append(([], oneHotMap_A[act], oneHotMap_R[res]))
            tracePredData.append(TracePredictionData(np.zeros(len(oneHotMap_A[act])), np.zeros(len(oneHotMap_R[res])), [], oneHotMap_A[act], trace.durations[i]))
        else:
            # Extend the known data with the one now known from previous event
            newHistory = np.append(data[-1][0], data[-1][1])
            newHistory = np.append(newHistory , data[-1][2])
            data.append((newHistory, oneHotMap_A[act], oneHotMap_R[res]))
            tracePredData.append(TracePredictionData(data[-1][1], data[-1][2], newHistory, oneHotMap_A[act], trace.durations[i]))
    
    return tracePredData


