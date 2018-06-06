import util.data_utils as pu
import util.utils as ut
from torch.utils.data import DataLoader
import argparse
import torch
import PIL
from torchvision import models, transforms
from model.CNNs import FineTuneModel
from model import model_utils as mu
from torchvision.datasets import ImageFolder
import os

from config import *

def main(args):

    log = ut.Logger()
    log.open(OUTPUT_FILE, mode='w')

    normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                      std=[0.229, 0.224, 0.225])

    input_trans = transforms.Compose([
            transforms.ColorJitter(brightness=0.2, contrast=0.2,saturation=0.2),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(15,resample=PIL.Image.BILINEAR, expand=True),
            transforms.Lambda(lambda x: ut.make_square(x)),
            transforms.Resize((args.img_size, args.img_size)),
            transforms.ToTensor(),
            normalize
    ])

    valid_trans = transforms.Compose([
            transforms.Lambda(lambda x: ut.make_square(x)),
            transforms.Resize((args.img_size, args.img_size)),
            transforms.ToTensor(),
            normalize
    ])

    # data loader for training
    dset_train = ImageFolder(root=TRAIN_DIR, transform=input_trans)
    labels = dset_train.classes  # all lables
    num_classes = len(labels)    # number of classes
    label_map = dict({dset_train.class_to_idx[name]: name for name in dset_train.classes})

    # data loader for validating
    dset_valid = ImageFolder(root=VALID_DIR, transform=valid_trans)

    #----------------------------------Configure------------------------------#
    # model arquitechture
    if args.pretrained:
        log.write("=> using pre-trained model '{}'\n".format(args.arch))
        model = models.__dict__[args.arch](pretrained=True)
    else:
        log.write("=> creating model '{}'\n".format(args.arch))
        model = models.__dict__[args.arch]()

    # freeze some layers
    for i, child in enumerate(model.children()):
        if i < 7:
            for param in child.parameters():
                param.requires_grad = False

    model = FineTuneModel(model, args.arch, num_classes)

    # optimizer
    """
    # SGD
    optimizer = torch.optim.SGD(model.parameters(),
                                 args.lr,
                                 momentum=args.momentum,
                                 weight_decay=args.weight_decay)
    """
    optimizer = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=args.lr)

    # criterion
    criterion = torch.nn.CrossEntropyLoss()

    if GPU_AVAIL:
        model = model.cuda()
        criterion = criterion.cuda()
        log.write("Using GPU...\n")

    #-----------------------------Data augmentation----------------------------#
    train_loader = DataLoader(dset_train,
                              batch_size=args.batch_size,
                              shuffle=True,
                              num_workers=args.workers,
                              pin_memory=GPU_AVAIL)
    valid_loader = DataLoader(dset_valid,
                              batch_size=args.batch_size,
                              shuffle=False,
                              num_workers=args.workers,
                              pin_memory=GPU_AVAIL)
    #--------------------------------------------------------------------------#


    #-----------------------------Training model ------------------------------#
    #model = mu.train(train_loader, valid_loader, model, criterion, optimizer, args,log)
    #-----------------------------Training model ------------------------------#
    if not args.testing:
        # load the best model
        checkpoint = torch.load(os.path.join(OUTPUT_WEIGHT_PATH, 'best_{}.pth.tar'.format(model.modelName)))
        model.load_state_dict(checkpoint['state_dict'])
    else:
        model, tr_loss, tr_acc, va_loss, va_acc, true_labels, pred_labels = mu.train(train_loader, valid_loader, model, criterion, optimizer, args,log)
        # generate output
        ut.loss_acc_plot(tr_loss, va_loss, 'Loss', OUTPUT_WEIGHT_PATH)
        ut.loss_acc_plot(tr_acc, va_acc, 'Accuracy', OUTPUT_WEIGHT_PATH)

        print(true_labels, pred_labels)

        true_labels = [labels[i] for i in true_labels]
        pred_labels = [labels[i] for i in pred_labels]
        #plot confusion matrix
        ut.plot_confusion_matrix(true_labels, pred_labels, labels, OUTPUT_WEIGHT_PATH)

    ut.plot_color_coding(labels, OUTPUT_WEIGHT_PATH)
    #--------------------------------------------------------------------------#

    #--------------------------------------------------------------------------#

    #-------------------------------- Testing ---------------------------------#

    mu.make_prediction_on_images(INPUT_TEST_DIR, OUTPUT_TEST_DIR, valid_trans, model, log)

    """
    dset_test = pu.DataLoader(None, TEST_DIR, valid_trans, labels)
    test_loader = DataLoader(dset_test,
                              batch_size=args.batch_size,
                              shuffle=False,
                              num_workers=args.workers,
                              pin_memory=GPU_AVAIL)
    mu.predict(test_loader, model, args, label_map, log)
    """
    #--------------------------------------------------------------------------#

    return 0


if __name__ == '__main__':
    model_names = sorted(name for name in models.__dict__
                if name.islower() and not name.startswith("__")
                   and callable(models.__dict__[name]))

    prs = argparse.ArgumentParser(description='Fish challenge')
    prs.add_argument('-message', default=' ', type=str, help='Message to describe experiment in spreadsheet')
    prs.add_argument('-img_size', default=224, type=int, help='image height (default: 224)')
    prs.add_argument('--arch', '-a', metavar='ARCH', default='resnet18',
                        choices=model_names, help='model architecture: ' +
                        ' | '.join(model_names) +
                        ' (default: resnet18)')
    prs.add_argument('-epochs', default=10, type=int, help='Number of total epochs to run')
    prs.add_argument('-lr_patience', default=3, type=int, help='Number of patience to update lr')
    prs.add_argument('-early_stop', default=5, type=int, help='Early stopping')
    prs.add_argument('-j', '--workers', default=2, type=int, metavar='N', help='Number of data loading workers')
    prs.add_argument('-lr', '--lr', default=0.001, type=float, metavar='LR', help='Initial learning rate')
    prs.add_argument('-b', '--batch_size', default=32, type=int, metavar='N', help='Mini-batch size (default: 16)')
    prs.add_argument('--weight_decay', '--wd', default=1e-4, type=float, metavar='W', help='weight decay (default: 1e-4)')
    prs.add_argument('--momentum', default=0.9, type=float, metavar='M', help='momentum')
    prs.add_argument('--pretrained', dest='pretrained', action='store_true', help='use pre-trained model')
    prs.add_argument('--testing', dest='testing', action='store_false', help='use a trained model')

    args = prs.parse_args()
    main(args)

    print('Everything was running correctly!')
