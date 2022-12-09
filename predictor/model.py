
import tensorflow as tf
from tensorflow import keras
from predictor.performer.performer import TransformerBlock, TokenAndPositionEmbedding, PositionEmbedding
import tensorflow.keras.layers as L
import tensorflow.keras.models as M
import os
import numpy as np
import time
import datetime
from tensorflow.python.keras.saving import hdf5_format
import h5py

class PredictionModel:
    def __init__(self, mapOH_A = {}, mapOH_R = {}):
        self.callbacks = []
        self.MapOH_A = mapOH_A
        self.MapOH_R = mapOH_R
        pass

    def __GetPerformerConfiguration1(self, inputs, outputSize):
        embed_dim = 30  # Embedding size for each token  => Set to 30 to match LSTM dimensionality
        num_heads = 4  # Number of attention heads
        ff_dim = 32  # Hidden layer size in feed forward network inside transformer
        method = 'linear'
        supports = 4
        
        embedding_layer = TokenAndPositionEmbedding(inputs.shape[-1], 200, embed_dim) # (In, CovabSize, Dimensions)
        x = embedding_layer(inputs)
        transformer_block = TransformerBlock(embed_dim, num_heads, ff_dim, method, supports)
        x = transformer_block(x)
        print(x.shape)
        #x = L.Dense(1, )(x) # Reduce dimensionality to reduce number of parameters
        #print(x.shape)
        x = L.Flatten()(x)
        x = L.Dense(outputSize, )(x) # make output (None, 30)
        
        return x

        



    def buildModel(self, regression, X_train_shape, y_train_shape, dropout, loss, context_shape):
        print(X_train_shape)
        inputs = L.Input(shape=X_train_shape[1], name='Input')
        inter = L.Dropout(dropout)(inputs, training=True)
        
        inter = self.__GetPerformerConfiguration1(inter, 30)


        inter = L.Dropout(dropout)(inter, training=True)

        if context_shape is not None:
            auxiliary_input = L.Input(shape=(context_shape[1],), name='aux_input')
            aux_inter = L.Dropout(dropout)(auxiliary_input, training=True)

            inter = L.concatenate([inter, aux_inter])
            inter = L.Dropout(dropout)(inter, training=True)

            if regression:
                outputs = L.Dense(y_train_shape[1], )(inter)
            else:
                outputs = L.Dense(y_train_shape[1], activation='softmax')(inter)
            model = tf.keras.Model(inputs=[inputs,auxiliary_input], outputs=outputs)
        else:
            if regression:
                outputs = L.Dense(y_train_shape[1], )(inter)
            else:
                outputs = L.Dense(y_train_shape[1], activation='softmax')(inter)
            model = tf.keras.Model(inputs=inputs, outputs=outputs)

        model.compile(loss=loss, optimizer='adam')
        model.summary()
        return model

    def Train(self, X_train, X_train_ctx, y_train, regression, loss, n_epochs = 100,
        y_normalize=False, 
        dropout = 0.05, 
        batch_size= 128, 
        context=True, 
        num_folds=10):

        """
            Constructor for the class implementing a Bayesian neural network
            trained with the probabilistic back propagation method.
            @param X_train      Matrix with the features for the training data.
            @param y_train      Vector with the target variables for the
                                training data.
            @param n_epochs     Numer of epochs for which to train the
                                network. The recommended value 40 should be
                                enough.
            @param normalize    Whether to normalize the input features. This
                                is recommended unles the input vector is for
                                example formed by binary features (a
                                fingerprint). In that case we do not recommend
                                to normalize the features.
            @param tau          Tau value used for regularization
            @param dropout      Dropout rate for all the dropout layers in the
                                network.
        """

        if y_normalize:
            self.mean_y_train = np.mean(y_train)
            self.std_y_train = np.std(y_train)

            y_train_normalized = (y_train - self.mean_y_train) / self.std_y_train
            y_train_normalized = np.array(y_train_normalized, ndmin = 2).T
        else:
            if len(y_train.shape) == 1:
                y_train_normalized = np.array(y_train, ndmin = 2).T
            else:
                y_train_normalized = y_train

        # Do we have a context vector?
        ctxShape = None
        if context:
            ctxShape = X_train_ctx.shape

        # Construct the model
        model = self.buildModel(regression=regression, X_train_shape=X_train.shape, y_train_shape=y_train_normalized.shape, dropout=dropout, loss=loss, context_shape=ctxShape)
        
        # We iterate the learning process
        start_time = time.time()
        if context:
            model.fit([X_train,X_train_ctx], y_train_normalized, batch_size=batch_size, epochs=n_epochs, verbose=2, validation_split=1/num_folds, callbacks=self.callbacks)
        else:
            model.fit(X_train, y_train_normalized, batch_size=batch_size, epochs=n_epochs, verbose=2, validation_split=1/num_folds, callbacks=self.callbacks)

        self.model = model
        self.running_time = time.time() - start_time
        # We are done!

    def Load(self, checkpoint_dir, name = None):
        if name is not None:
            modelPath = f"{os.path.join(checkpoint_dir, name)}.h5"
        else:
            # A full path might have been provided
            modelPath = M.load_model(checkpoint_dir)
            
        with h5py.File(modelPath, mode='r') as f:
            self.MapOH_A = f.attrs['MapOH_A']
            self.MapOH_R = f.attrs['MapOH_R']
            self.model = hdf5_format.load_model_from_hdf5(f)
        

    def Save(self, checkpoint_dir, name):
        with h5py.File(f"{os.path.join(checkpoint_dir, name)}.h5", mode='w') as f:
            hdf5_format.save_model_to_hdf5(self.model, f)
            f.attrs['MapOH_A'] = self.MapOH_A
            f.attrs['MapOH_R'] = self.MapOH_R

    def RegisterCallbackTF(self, cb):
        try:
            iterator = iter(cb)
        except TypeError:
            self.callbacks.append(cb)
        else:
            for x in cb:    
                self.callbacks.append(x)

    def Predict(self, X_test, X_test_ctx=None, context=True):
        """
            Function for making predictions with the Bayesian neural network.
            @param X_test   The matrix of features for the test data


            @return m       The predictive mean for the test target variables.
            @return v       The predictive variance for the test target
                            variables.
            @return v_noise The estimated variance for the additive noise.
        """

        X_test = np.array(X_test, ndmin = 3)
        model = self.model
        
        T = 10
        if context==True:
            X_test_ctx = np.array(X_test_ctx, ndmin=2)
            Yt_hat = np.array([model.predict([X_test, X_test_ctx], batch_size=1, verbose=0) for _ in range(T)])
        else:
            Yt_hat = np.array([model.predict(X_test, batch_size=1, verbose=0) for _ in range(T)])
        
        #Yt_hat = Yt_hat * self.std_y_train + self.mean_y_train
        
        regression=False
        MC_pred = np.mean(Yt_hat, 0)
        
        if regression:
            MC_uncertainty = np.std(Yt_hat, 0)
        else:
            MC_uncertainty = list()
            for i in range(Yt_hat.shape[2]):
                MC_uncertainty.append(np.std(Yt_hat[:,:,i].squeeze(),0))
        #rmse = np.mean((y_test.squeeze() - MC_pred.squeeze())**2.)**0.5

        # We are done!
        return MC_pred, MC_uncertainty
        