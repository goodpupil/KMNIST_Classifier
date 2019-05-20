# imports
from livelossplot import PlotLosses
from sklearn.metrics import accuracy_score
from torch.utils.data import Dataset 
import numpy as np
import random
import torch
import torch.nn as nn
import torch.nn.functional as F


# define the seed function
def set_seed(seed):
    """
    Use this to set ALL the random seeds to a fixed value and take out any randomness from cuda kernels
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    torch.backends.cudnn.benchmark = False  ##uses the inbuilt cudnn auto-tuner to find the fastest convolution algorithms. -
    torch.backends.cudnn.enabled   = False

    return True
	
# define the training wrapper
class train_wrapper():
    """
    Class that keeps a model, its optimiser and dataloaders together.
    Stores the train, validate and evaluate functions for training as well
    as some other useful methods to carry out the training with a love plot
    and save the model.
    """
    
    def __init__(self, model, optimizer, train_loader, validate_loader,
				 criterion=nn.CrossEntropyLoss(), device="cpu", test_transform=False):
        "Stores the parameters on the class instance for later methods"
        
        for arg in ["model", "optimizer", "train_loader", "validate_loader",
					"criterion", "device", "test_transform"]:
            exec("self." + arg + "=" + arg)
        return
    
    
    def train(self):
        "Train a single epoch"
        
        # set the model expect a backward pass
        self.model.train()
        
        train_loss, train_accuracy = 0, 0
        
        # for every training batch
        for X, y in self.train_loader:
            
            # put the samples on the device
            X, y = X.to(self.device), y.to(self.device)
            
            # zero the gradent
            self.optimizer.zero_grad()
            
            # find the model output with current parameters
            output = self.model(X)
            
            # caclulate the loss for to the expect output
            loss = self.criterion(output, y)
            
            # propagate the gradients though the network
            loss.backward()
            
            # store the loss (scaled by batch size for averaging)
            train_loss += loss * X.size(0)
            
            # find the predictions from this output
            y_pred = F.log_softmax(output, dim=1).max(1)[1]
            
            # compare to expected output to find the accuracy
            train_accuracy += accuracy_score(y.cpu().numpy(), y_pred.detach().cpu().numpy())*X.size(0)
            
            # improve the parameters
            self.optimizer.step()

        # return the mean loss and accuracy of this epoch
        N_samp = len(self.train_loader.dataset)
        return train_loss/N_samp, train_accuracy/N_samp
    
    
    def validate(self):
        """
        Find the loss and accuracy of the current model parameters to the
        validation data set
        """
        
        # if no validation set present return zeros
        if self.validate_loader == None:
            return torch.tensor(0.), torch.tensor(0.)
        
        # set the model to not expect a backward pass
        self.model.eval()
        
        validation_loss, validation_accuracy = 0., 0.
        
        # for every validate batch
        for X, y in self.validate_loader:
            
            # tell the optimizer not to store gradients
            with torch.no_grad():
                
                # put the samples on the device
                X, y = X.to(self.device), y.to(self.device)
                
                # find the model output with current parameters
                output = self.model(X)
                
                # caclulate the loss for to the expect output
                loss = self.criterion(output, y)
                
                # store the loss (scaled by batch size for averaging)
                validation_loss += loss * X.size(0)
                
                # find the predictions from this output
                y_pred = F.log_softmax(output, dim=1).max(1)[1]
                
                # compare to expected output to find the accuracy
                validation_accuracy += accuracy_score(y.cpu().numpy(), y_pred.cpu().numpy())*X.size(0)
        
        # return the mean loss and accuracy of this epoch
        N_samp = len(self.validate_loader.dataset)
        return validation_loss/N_samp, validation_accuracy/N_samp
    
    
    def evaluate(self, test_data, prob_output=True):
        """
        Find the prediction of the current model parameters with the test
        data set and return both the predicted and actual labels
        """
        
	# normalise the test data with validates transformation
        if self.test_transform:
	    test_data = self.test_transform(test_data)
	
        # set the model to not expect a backward pass
        self.model.eval()
        
        y_preds = []
        
        # for every test batch
        for X, in self.test_loader:
        
            # tell the optimizer not to store gradients
            with torch.no_grad():
                
                # put the samples on the device
                X = X.to(self.device)
                
                # find the model output with current parameters
                output = self.model(X)
                
                # find the predictions from this output
                if not prob_output:
			y_pred = F.log_softmax(output, dim=1).max(1)[1]

                # store the predicted and actual outcomes
                y_preds.append(y_pred.cpu().numpy())

        # return the list of predictions and actual targets
        return np.concatenate(y_preds, 0)
    
    
    def train_model(self, epochs):
        """
        Do a live plot of the training accuracy and loss as the model is trained
        """
        
        # store the liveloss as it holds all our logs, useful for later
        self.liveloss = PlotLosses()
        
        for epoch in range(epochs):
            logs = {}
            train_loss, train_accuracy = self.train()

            logs['' + 'log loss'] = train_loss.item()
            logs['' + 'accuracy'] = train_accuracy.item()

            validation_loss, validation_accuracy = self.validate()
            logs['val_' + 'log loss'] = validation_loss.item()
            logs['val_' + 'accuracy'] = validation_accuracy.item()

            self.liveloss.update(logs)
            self.liveloss.draw()
            
        print("Training Finished")
        return
    
    
    def save_model(self, name, path=F"/content/gdrive/My Drive/models/", only_params=False):
        """
        Pickel either the whole model or its parameter dictionary
        via torch's save methods
        """
        
        if only_params:
            torch.save(self.model.state_dict(), path + name)
        else:
            torch.save(self.model, path + name)
        
        print("saved to " + path + name)
    

    def num_model_params(self):
        n_params = sum([t.detach().numpy().size 
                        for t in self.model.parameters()])
        print("Number of model Parameters: ", n_params)
        return n_params



def save_csv(data, file, path='/', header="Id,Category"):
    
    f = open(path + file + ".csv", 'w')
    assert (not f.closed), "could not open file"
    
    f.write(header + "\n")
    for i, d in enumerate(data):
        d = int(d)
        f.write(str(i) + "," + str(d) + "\n")
    
    f.close()
    print("successfully saved in " + path + file + ".csv")
    return 
	

class CustomImageTensorDataset(Dataset):
    def __init__(self, data, targets, transform=None):
        """
        Args:
            data (Tensor): A tensor containing the data e.g. images
            targets (Tensor): A tensor containing all the labels
            transform (callable, optional): Optional transform to be applied
                on a sample.
        """
        self.data = data
        self.targets = targets
        self.transform = transform

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        sample, label = self.data[idx], self.targets[idx]
        if self.transform:
            sample = self.transform(sample)

        return sample, label

