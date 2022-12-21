import argparse
import pickle
from datetime import datetime
from predictor.model import PredictionModel
import signal
from predictor.dataPrep import PrepareEventlogForActivityPrediction
from simulation.objects.enums import TimestampModes
import tensorflow as tf
import os
import numpy as np

model = None
scriptArgs = None


def handler(signum, frame):
    global model
    global scriptArgs
    print('TODO: Save model checkpoint on interrupt')
    exit(1)    
signal.signal(signal.SIGINT, handler)


def argsParse():
    global scriptArgs   
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--log', default='../logs/log.xes', type=str, help="The path to the event-log to be loaded")
    parser.add_argument('-c', '--checkpointDir', default='predictor/checkpoints', type=str, help="The path to the folder storing the model checkpoints")
    parser.add_argument('-m', '--modelName', default=None, type=str, help="The name of the model")
    parser.add_argument('-t','--task', default='next_activity', type=str, choices=['next_activity', 'duration'], help="Select what should be predicted: next activity or activity duration")
    parser.add_argument('--CTX', default=False, action='store_true', help="Use context (all previous events of trace) for prediction")
    parser.add_argument('-v', '--verbose', default=False, action='store_true', help="Display additional runtime information")
    scriptArgs = parser.parse_args()
    return scriptArgs


def SetTrainingCallbacks(model, args):
    early_stopping   = tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=20)
    model_checkpoint = tf.keras.callbacks.ModelCheckpoint(f'{os.path.join(args.checkpointDir, args.modelName)}.h5', monitor='val_loss', verbose=0, save_best_only=True, save_weights_only=False, mode='auto')
    lr_reducer       = tf.keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=10, verbose=0, mode='auto', min_delta=0.0001, cooldown=0, min_lr=0)
    
    logs = "logs/" + datetime.now().strftime("%Y%m%d-%H%M%S")
    tboard_callback = tf.keras.callbacks.TensorBoard(log_dir = logs,histogram_freq = 1,profile_batch = '500,520')
    model.RegisterCallbackTF([early_stopping, model_checkpoint, lr_reducer])#,tboard_callback]


def main():
    global model
    args = argsParse()



    logData, A, R = PrepareEventlogForActivityPrediction(args.log, 'ts')
    model = PredictionModel(A, R)
    model.GenerateOneHotMappings(A, R)
    SetTrainingCallbacks(model, args)
    
    
    # Split the data into predictors, targets and context
    train_X = np.array([np.append(d.CurrentActivity, d.CurrentResource) for d in logData])
    if args.CTX:
        train_context_X = [d.HistoricActResTuples for d in logData]
        maxLen = max([len(x) for x in train_context_X])
        train_context_X = np.array([np.append(np.zeros(maxLen - len(x)), x) for x in train_context_X])
    else:
        train_context_X = None
    train_Y = np.array([d.NextActivity if args.task == 'next_activity' else d.CurrentActivityDuration for d in logData])


    # Set loss function for each task
    if args.task == 'next_activity':
        loss = 'categorical_crossentropy'
        regression = False
    elif args.task == 'duration':
        loss = 'mae'
        regression = True


    # Run the training
    model.Train(train_X, train_context_X, train_Y, regression, loss, batch_size=256, num_folds=10, context=(train_context_X is not None))
    model.Save(args.checkpointDir, args.modelName)


if __name__ == '__main__':
    main()