import numpy as np
import torch
import torch.nn.functional as F
import torchvision.datasets as datasets
from torchvision.transforms import (CenterCrop, Compose, Normalize, Resize,
                                    ToTensor)

from data import create_loader
from model import create_model
from test_arguments import Arguments
from utils import calculate_f1_score, multiclass_roc_auc_score

#-----------------------------------------
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
#-----------------------------------------

args = Arguments().parse()

args.phase = 'test'

if args.pretrained:
    transforms = Compose([Resize(args.input_size), CenterCrop(args.input_size), ToTensor(), Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
else:
    transforms = Compose([Resize(args.input_size), CenterCrop(args.input_size), ToTensor()])

pos_dataset = datasets.ImageFolder(args.pos_root)
pos_dataset.transform = transforms
pos_loader = torch.utils.data.DataLoader(pos_dataset, batch_size=1, num_workers=4, shuffle=False, drop_last=False)

neg_dataset = datasets.ImageFolder(args.neg_root)
neg_dataset.transform = transforms
neg_loader = torch.utils.data.DataLoader(neg_dataset, batch_size=1, num_workers=4, shuffle=False, drop_last=False)

nl = '\n'
print(f'There are a total number of {len(pos_loader)} images in the positive test data set and {len(neg_loader)} images in the negative test data set.{nl}')

if args.arch != 'AmirNet_DO' and args.arch != 'AmirNet_CDO' and args.arch != 'AmirNet_VDO':
        raise ValueError('The network you have selected cannot be used to obtain uncertainty.')


model = create_model(args, None, pos_loader.dataset.classes)
model.set_up(args)

network = model.return_model()

print(f'{nl}Processing the positive test images has begun..{nl}')

gts = []
preds = []
accuracy = 0.0

uncertainty_list = []
confidence_list = []

with torch.no_grad():
        for j, data in enumerate(pos_loader):

                image, gt = data

                image = image.to(device)
                gt = gt.to(device)

                network.train()

                out_list = []

                for i in range(args.num_samples):
                        out_list.append(torch.unsqueeze(F.softmax(network(image), dim=1), 0))

                output_mean = torch.cat(out_list, 0).mean(0) # 1 X Num classes
                confidence = float(output_mean.cpu().numpy().max())

                predicted = output_mean.cpu().numpy().argmax()
                # uncertainty value for the predicted label, which is obviously wrong
                # uncertainty can also be calculated for the entire output (not just the predicted class), but we empirically find this uncertainty to be a cleaner indication of uncertainty.
                uncertainty = float(torch.cat(out_list, 0)[:, :, predicted].var(0).cpu().numpy()) # Num classes X 1

                uncertainty_list.append(uncertainty)
                confidence_list.append(confidence)

                accuracy += predicted == (gt.item())            
                gts.append(gt.item())
                preds.append(predicted)

accuracy /= len(pos_loader)
f1 = calculate_f1_score(gts, preds)
auc = multiclass_roc_auc_score(gts, preds)

print('Positive test data processing completed.')
print(f'Accuracy: {accuracy:.4f} -- F1 Score: {f1:.4f} -- AUC: {auc:.4f} -- Uncertainty: {np.mean(uncertainty_list)}')

print(f'{nl}Processing the negative test images has begun..{nl}')

uncertainty_list = []
confidence_list = []

with torch.no_grad():
        for j, data in enumerate(neg_loader):

                image, _ = data
                image = image.to(device)

                network.train()

                out_list = []

                for i in range(args.num_samples):
                        out_list.append(torch.unsqueeze(F.softmax(network(image), dim=1), 0))

                output_mean = torch.cat(out_list, 0).mean(0) # 1 X Num classes
                confidence = float(output_mean.cpu().numpy().max())

                predicted = output_mean.cpu().numpy().argmax()
                # uncertainty value for the predicted label, which is obviously wrong even if predicted with high confidence, as all the data are negative
                # uncertainty can also be calculated for the entire output (not just the predicted class), but we empirically find this to be a cleaner indication of uncertainty.
                uncertainty = float(torch.cat(out_list, 0)[:, :, predicted].var(0).cpu().numpy()) # Num classes X 1

                uncertainty_list.append(uncertainty)
                confidence_list.append(confidence)

print('Negative test data processing completed.')
print(f'Uncertainty: {np.mean(uncertainty_list)}')
