import numpy as np
import os
import torch
from torch.autograd import Variable
import torch.nn as nn
import torch.utils.data as data
from config import get_test_config
from data import SHREC21Dataset
from models import MeshNet
from tqdm import tqdm
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-w', '--weight',
                    type=str,
                    help='path to the trained weight')
parser.add_argument('-t', '--task',
                    type=str,
                    help='[Culture|Shape]')
parser.add_argument('-f', '--fold',
                    type=int,
                    help='fold index')
parser.add_argument('-r', '--data_root',
                    type=str,
                    help='path to MeshNet')
parser.add_argument('--num_faces',
                    type=int,
                    help='number of faces')
args = parser.parse_args()

cfg = get_test_config()
cfg['dataset']['data_root'] = args.data_root
cfg['dataset']['max_faces'] = args.num_faces

os.environ['CUDA_VISIBLE_DEVICES'] = cfg['cuda_devices']


data_set = {
    x: SHREC21Dataset(cfg=cfg['dataset'], part=x, return_index=True) for x in ['train', 'test']
}
data_loader = {
    x: data.DataLoader(data_set[x], batch_size=1, num_workers=8, shuffle=False, pin_memory=True)
    for x in ['train', 'test']
}

embed_dict = {}
embed_npy = []
def test_model(model):
    with torch.no_grad():
        correct_num = 0
        ft_all, lbl_all = None, None
        for x in ['train', 'test']:
            for i, (centers, corners, normals, neighbor_index, targets, filename) in enumerate(tqdm(data_loader[x])):
                file_id = int(filename[0][:-4])
                centers = Variable(torch.cuda.FloatTensor(centers.cuda()))
                corners = Variable(torch.cuda.FloatTensor(corners.cuda()))
                normals = Variable(torch.cuda.FloatTensor(normals.cuda()))
                neighbor_index = Variable(torch.cuda.LongTensor(neighbor_index.cuda()))
                targets = Variable(torch.cuda.LongTensor(targets.cuda()))

                _, feas = model(centers, corners, normals, neighbor_index)
                ft_all = feas.cpu().squeeze(0).numpy()
                embed_dict[file_id] = ft_all

        ids = sorted(list(embed_dict.keys()))
        for i in ids:
            embed_npy.append(embed_dict[i])

    print(f'Number of embeddings: {len(ids)}')
    np.save(f'./results/{args.fold}/embed_fold_{args.fold}.npy',embed_npy)

if __name__ == '__main__':

    if args.task == 'Shape':
        num_classes = 8
    else:
        num_classes = 6


    model = MeshNet(cfg=cfg['MeshNet'], num_classes=num_classes, require_fea=True)
    model.cuda()
    model = nn.DataParallel(model)
    model.load_state_dict(torch.load(args.weight))
    
    if not os.path.exists(f'./results/{args.fold}'):
        os.makedirs(f'./results/{args.fold}')
    model.eval()

    test_model(model)
