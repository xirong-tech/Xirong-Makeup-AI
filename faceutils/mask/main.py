#!/usr/bin/python
# -*- encoding: utf-8 -*-
import os.path as osp

import numpy as np
import cv2
from PIL import Image
import torch
import torchvision.transforms as transforms

from faceutils.mask.model  import BiSeNet


class FaceParser:
    def __init__(self, device="cpu"):
        mapper = [0, 1, 2, 3, 4, 5, 0, 11, 12, 0, 6, 8, 7, 9, 13, 0, 0, 10, 0]
        self.device = device
        # 修改 self.dic 使其变成二维张量
        self.dic = torch.tensor(mapper, device=device).unsqueeze(1).float()#这段代码的目的是创建一个二维的浮点型张量，其中包含了映射器mapper中的值，并且这个张量被放置在指定的设备上。这个张量在后续的计算中可能会被用作一个查找表，例如在神经网络的嵌入层中。
        save_pth = osp.split(osp.realpath(__file__))[0] + '/resnet.pth'##首先确定模型权重文件的路径save_pth，通过获取当前文件所在目录并拼接上'/resnet.pth'得到。

        net = BiSeNet(n_classes=19)#实例化BiSeNet模型，指定类别数量为19
        net.load_state_dict(torch.load(save_pth, map_location=torch.device('cpu'), weights_only=True))#加载模型权重文件，使用torch.load函数加载模型权重文件，并且通过map_location参数将模型权重文件加载到指定的设备上。
        self.net = net.to(device).eval()#这行代码将之前创建的 BiSeNet 模型实例 net 移动到指定的设备 device 上，并且设置为评估模式（eval()）。在评估模式下，模型的参数不会被更新，这通常用于模型的推理阶段。
        self.to_tensor = transforms.Compose([
            transforms.ToTensor(),#将图像转换为 PyTorch 张量。
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),#对图像进行标准化处理，使用给定的均值和标准差。
        ])


    def parse(self, image: Image):
        assert image.shape[:2] == (512, 512)#确保输入的图像的尺寸为512x512
        with torch.no_grad():#在这个代码块中，使用torch.no_grad()上下文管理器来禁止梯度计算，以减少内存消耗并提高计算效率。
            image = self.to_tensor(image).to(self.device)#首先将输入的PIL图像通过self.to_tensor转换为张量并移动到指定的设备（self.device）上
            image = torch.unsqueeze(image, 0)#在维度 0 上增加一个维度，将图像张量的形状变为(1, C, H, W)的形式（其中C表示通道数，H和W分别表示图像的高度和宽度），符合模型输入的批量维度要求（即使这里只有单张图像，也以批量为 1 的形式输入）。
            out = self.net(image)[0]#将图像输入到模型中，得到模型的输出out。由于模型输出是一个包含两个元素的元组，因此使用[0]来获取模型的输出张量。
            parsing = out.squeeze(0).argmax(0)#对模型输出张量进行降维操作，将其形状变为(H, W)的形式。然后使用argmax(0)操作，找到每个像素位置上的最大概率对应的类别索引。这样得到的parsing张量的形状为(H, W)，其中每个位置的值表示该位置所属的类别索引。

        parsing = torch.nn.functional.embedding(parsing, self.dic)#使用torch.nn.functional.embedding函数，根据前面定义的self.dic张量对初步解析结果parsing进行嵌入操作
        return parsing.float()

