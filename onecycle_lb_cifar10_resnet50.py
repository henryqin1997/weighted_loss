'''Train CIFAR10 with PyTorch.'''
import torch
import torch.nn as nn
import torch.optim as optim
import torch.backends.cudnn as cudnn

import torchvision
import torchvision.transforms as transforms

import os
import argparse
import datetime

from models import *
# from utils import progress_bar
import json


parser = argparse.ArgumentParser(description='PyTorch CIFAR10 Training')
parser.add_argument('--lr', default=1, type=float, help='learning rate')
parser.add_argument('--resume', '-r', action='store_true',
                    help='resume from checkpoint')
parser.add_argument('--batch-size', type=int, default=8192, metavar='N',
                    help='input batch size for training (default: 128)')
parser.add_argument('--test-batch-size', type=int, default=128, metavar='N',
                    help='input batch size for testing (default: 128)')
parser.add_argument('--warmup-epochs', type=int, default=5, metavar='WE',
                    help='number of warmup epochs (default: 5)')
parser.add_argument('--lr-decay', nargs='+', type=int, default=[50, 75],
                    help='epoch intervals to decay lr')
parser.add_argument('--momentum', type=float, default=0.9, metavar='M',
                    help='SGD momentum (default: 0.9)')
parser.add_argument('--weight-decay', type=float, default=5e-4, metavar='W',
                    help='SGD weight decay (default: 5e-4)')
parser.add_argument('--optimizer',type=str,default='sgd',
                    help='different optimizers')
parser.add_argument('--max-lr',default=0.1,type=float)
parser.add_argument('--div-factor',default=25,type=float)
parser.add_argument('--final-div',default=10000,type=float)
parser.add_argument('--num-epoch',default=150,type=int)
parser.add_argument('--pct-start',default=0.3,type=float)
parser.add_argument('--weighted-loss',default=1,type=int)


args = parser.parse_args()

device = 'cuda' if torch.cuda.is_available() else 'cpu'
best_acc = 0  # best test accuracy
start_epoch = 0  # start from epoch 0 or last checkpoint epoch

# Data
print('==> Preparing data..')
transform_train = transforms.Compose([
    transforms.RandomCrop(32, padding=4),
    transforms.RandomHorizontalFlip(),
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
])

transform_test = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
])

trainset = torchvision.datasets.CIFAR10(
    root='/tmp/cifar10', train=True, download=True, transform=transform_train)
trainloader = torch.utils.data.DataLoader(
    trainset, batch_size=128)

testset = torchvision.datasets.CIFAR10(
    root='/tmp/cifar10', train=False, download=True, transform=transform_test)
testloader = torch.utils.data.DataLoader(
    testset, batch_size=100, shuffle=False)

classes = ('plane', 'car', 'bird', 'cat', 'deer',
           'dog', 'frog', 'horse', 'ship', 'truck')

# Model
print('==> Building model..')
# net = VGG('VGG19')
# net = ResNet18()
# net = PreActResNet18()
# net = GoogLeNet()
# net = DenseNet121()
# net = ResNeXt29_2x64d()
# net = MobileNet()
# net = MobileNetV2()
# net = DPN92()
# net = ShuffleNetG2()
# net = SENet18()
# net = ShuffleNetV2(1)
# net = EfficientNetB0()
# net = RegNetX_200MF()
net = ResNet50()
net = net.to(device)
if device == 'cuda':
    net = torch.nn.DataParallel(net)
    cudnn.benchmark = True

criterion = nn.CrossEntropyLoss()

def myweightedloss(y_hat, y_true):
    unaveraged_loss = F.cross_entropy(F.log_softmax(y_hat, 1), y_true, weight=None, reduce=False, reduction="mean")
    loss = unaveraged_loss.square()
    return torch.mean(loss)

def myweightedloss2(y_hat, y_true):
    unaveraged_loss = F.cross_entropy(F.log_softmax(y_hat, 1), y_true, weight=None, reduce=False, reduction="mean")
    loss = unaveraged_loss.square()
    return torch.sum(loss)/torch.sum(unaveraged_loss)

def myweightedloss3(y_hat, y_true):
    unaveraged_loss = F.cross_entropy(F.log_softmax(y_hat, 1), y_true, weight=None, reduce=False, reduction="mean")
    loss = unaveraged_loss.square()
    return torch.mean(loss) / max(torch.mean(unaveraged_loss),1)

if args.weighted_loss==1:
    weightedloss = myweightedloss
elif args.weighted_loss==2:
    weightedloss = myweightedloss2
elif args.weighted_loss==3:
    weightedloss = myweightedloss3
else:
    weightedloss = criterion

if args.optimizer.lower()=='sgd':
    optimizer = optim.SGD(net.parameters(), lr=args.lr, weight_decay=args.weight_decay)
if args.optimizer.lower()=='sgdwm':
    optimizer = optim.SGD(net.parameters(), lr=args.lr, momentum=args.momentum,
                      weight_decay=args.weight_decay)
elif args.optimizer.lower()=='adam':
    optimizer = torch.optim.Adam(net.parameters(), lr=args.lr,
                      weight_decay=args.weight_decay)
elif args.optimizer.lower() == 'rmsprop':
    optimizer = optim.RMSprop(net.parameters(),lr=args.lr, momentum=args.momentum,
                      weight_decay=args.weight_decay)
elif args.optimizer.lower() == 'adagrad':
    optimizer = optim.Adagrad(net.parameters(), lr=args.lr, weight_decay=args.weight_decay)
elif args.optimizer.lower() == 'radam':
    from radam import RAdam
    optimizer = RAdam(net.parameters(),lr=args.lr,weight_decay=args.weight_decay)
elif args.optimizer.lower() == 'lars':#no tensorboardX
    from lars import LARS
    optimizer = LARS(net.parameters(), lr=args.lr,momentum=args.momentum,weight_decay=1e-4)
elif args.optimizer.lower() == 'lamb':
    from lamb import Lamb
    optimizer  = Lamb(net.parameters(),lr=args.lr,weight_decay=args.weight_decay)
elif args.optimizer.lower() == 'novograd':
    from novograd import NovoGrad
    optimizer = NovoGrad(net.parameters(), lr=args.lr,weight_decay=args.weight_decay)
else:
    optimizer = optim.SGD(net.parameters(), lr=args.lr, momentum=args.momentum,
                          weight_decay=args.weight_decay)
# lrs = create_lr_scheduler(args.warmup_epochs, args.lr_decay)
# lr_scheduler = LambdaLR(optimizer,lrs)
# lr_scheduler = torch.optim.lr_scheduler.MultiStepLR(optimizer, args.lr_decay, gamma=0.1)

batch_acumulate = args.batch_size//128
batch_per_step = len(trainloader)//batch_acumulate+int(len(trainloader)%batch_acumulate>0)

lr_scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer,args.max_lr,steps_per_epoch=batch_per_step,
                                                   epochs=args.num_epoch,div_factor=args.div_factor,final_div_factor=args.final_div,pct_start=args.pct_start)
train_acc = []
valid_acc = []

# Training
def train(epoch):
    print('\nEpoch: %d' % epoch)
    net.train()
    train_loss = 0
    count = 0
    correct = 0
    total = 0
    for batch_idx, (inputs, targets) in enumerate(trainloader):
        inputs, targets = inputs.to(device), targets.to(device)
        outputs = net(inputs)
        loss = weightedloss(outputs, targets)
        loss.backward()
        if batch_idx % batch_acumulate==batch_acumulate-1 or batch_idx==len(trainloader)-1:
            optimizer.step()
            optimizer.zero_grad()
            lr_scheduler.step()
        train_loss += loss.item()
        count+=1
        _, predicted = outputs.max(1)
        total += targets.size(0)
        correct += predicted.eq(targets).sum().item()
        if batch_idx % batch_acumulate == batch_acumulate - 1 or batch_idx == len(trainloader) - 1:
            # progress_bar(batch_idx//batch_acumulate if batch_idx!=len(trainloader) - 1 else batch_per_step, batch_per_step, 'Loss: %.3f | Acc: %.3f%% (%d/%d)'
            #          % (train_loss / (count), 100. * correct / total, correct, total))
            train_loss, count = 0, 0
    train_acc.append(correct/total)

def test(epoch):
    global best_acc
    net.eval()
    test_loss = 0
    correct = 0
    total = 0
    with torch.no_grad():
        for batch_idx, (inputs, targets) in enumerate(testloader):
            inputs, targets = inputs.to(device), targets.to(device)
            outputs = net(inputs)
            loss = criterion(outputs, targets)

            test_loss += loss.item()
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()

            # progress_bar(batch_idx, len(testloader), 'Loss: %.3f | Acc: %.3f%% (%d/%d)'
            #              % (test_loss/(batch_idx+1), 100.*correct/total, correct, total))

    # Save checkpoint.
    valid_acc.append(correct/total)

for epoch in range(args.num_epoch):
    train(epoch)
    test(epoch)
fn = '{}{}-{}-epoch{}-batchsize{}-pct{}-{}-loss{}_onecycle_log.json'.format(
                                args.optimizer,str(args.max_lr/args.div_factor),
                                str(args.max_lr),args.num_epoch,args.batch_size,args.pct_start,
                                datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'),args.weighted_loss
                            )
file = open(fn,'w+')
json.dump([train_acc,valid_acc],file)