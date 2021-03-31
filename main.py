import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
import time
import pdb
import sys
import os

from fcn import Segnet
from r2unet import U_Net, R2U_Net, RecU_Net, ResU_Net
#from deeplabv3_torchvision import DeepLabHead
from deeplabv3 import DeepLabV3
from dataloader import load_dataset
from metrics import Metrics
from vis import Vis

from torchvision.models.segmentation.segmentation import deeplabv3_resnet50

expt_logdir = sys.argv[1]
os.makedirs(expt_logdir, exist_ok=True)

#Dataset parameters
num_workers = 8
batch_size = 16
n_classes = 20
img_size = 224 
test_split = 'val'

# Training parameters
epochs = 300 #use 200 
lr = 0.001
decayRate = 0.96
#TODO weight decay, plot results for validation data

# Logging options
i_save = 50#save model after every i_save epochs
i_vis = 10
rows, cols = 5, 2 #Show 10 images in the dataset along with target and predicted masks

# Setting up the device
device = torch.device("cuda")# if torch.cuda.is_available() else "cpu")
num_gpu = list(range(torch.cuda.device_count()))  

#Loading training and testing data
trainloader, train_dst = load_dataset(batch_size, num_workers, split='train')
testloader, test_dst = load_dataset(batch_size, num_workers, split=test_split)

# Creating an instance of the model 
#model = Segnet(n_classes) #Fully Convolutional Networks
#model = U_Net(img_ch=3,output_ch=n_classes) #U Network
#model = R2U_Net(img_ch=3,output_ch=n_classes,t=2) #Residual Recurrent U Network, R2Unet (t=2)
#model = R2U_Net(img_ch=3,output_ch=n_classes,t=3) #Residual Recurrent U Network, R2Unet (t=3)
#model = RecU_Net(img_ch=3,output_ch=n_classes,t=2) #Recurrent U Network, RecUnet (t=2)
#model = ResU_Net(img_ch=3,output_ch=n_classes) #Residual U Network, ResUnet 
#model = DeepLabV3(n_classes, 'vgg') #DeepLabV3 VGG backbone
model = DeepLabV3(n_classes, 'resnet') #DeepLabV3 Resnet backbone

print('Experiment logs for model: {}'.format(model.__class__.__name__))

model = nn.DataParallel(model, device_ids=num_gpu).to(device)
# loss function
loss_f = nn.CrossEntropyLoss() #TODO s ignore_index required? ignore_index=19

# optimizer variable
opt = optim.Adam(model.parameters(), lr=lr) 
lr_scheduler = optim.lr_scheduler.ExponentialLR(optimizer=opt, gamma=decayRate)
#torch.optim.lr_scheduler.StepLR(optimizer,step_size=3, gamma=0.1)

#TODO random seed
#Visualization of train and test data
train_vis = Vis(train_dst, expt_logdir, rows, cols)
test_vis = Vis(test_dst, expt_logdir, rows, cols)

#Metrics calculator for train and test data
train_metrics = Metrics(n_classes, trainloader, 'train', device, expt_logdir)
test_metrics = Metrics(n_classes, testloader, test_split, device, expt_logdir)

epoch = -1
train_metrics.compute(epoch, model)
train_metrics.plot_scalar_metrics(epoch)
train_metrics.plot_roc(epoch) 
train_vis.visualize(epoch, model)

test_metrics.compute(epoch, model)
test_metrics.plot_scalar_metrics(epoch)
test_metrics.plot_roc(epoch) 
test_vis.visualize(epoch, model)

#Training
losses = []
for epoch in range(epochs):
    st = time.time()
    model.train()
    for i, (inputs, labels) in enumerate(trainloader):
        opt.zero_grad()
        inputs = inputs.to(device)
        labels = labels.to(device)
        predictions = model(inputs)
        loss = loss_f(predictions, labels)
        loss.backward()
        opt.step()
        if i % 20 == 0:
            print("Finish iter: {}, loss {}".format(i, loss.data))
    lr_scheduler.step()
    losses.append(loss)
    print("Training epoch: {}, loss: {}, time elapsed: {},".format(epoch, loss, time.time() - st))
    
    train_metrics.compute(epoch, model)
    test_metrics.compute(epoch, model)
    
    if epoch % i_save == 0:
        torch.save(model.state_dict(), os.path.join(expt_logdir, "{}.tar".format(epoch))) #file name example: '0.tar'
    if epoch % i_vis == 0:                               # Metric calculation and visualization
        test_metrics.plot_scalar_metrics(epoch) 
        test_metrics.plot_roc(epoch) 
        test_vis.visualize(epoch, model)
        
        train_metrics.plot_scalar_metrics(epoch) 
        train_metrics.plot_roc(epoch) 
        train_vis.visualize(epoch, model)    
        
        train_metrics.plot_loss(epoch, losses) 
        
