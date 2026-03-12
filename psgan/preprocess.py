#!/usr/bin/python
# -*- encoding: utf-8 -*-
import os.path as osp
pwd = osp.split(osp.realpath(__file__))[0]
import sys
sys.path.append(pwd + '/..')

import cv2
import numpy as np
from PIL import Image
import torch
from torch.autograd import Variable
import torch.nn.functional as F
from torch.backends import cudnn
from torchvision import transforms

import faceutils as futils

transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize([0.5,0.5,0.5],[0.5,0.5,0.5])])


def ToTensor(pic):
    # handle PIL Image
    if pic.mode == 'I':
        img = torch.from_numpy(np.array(pic, np.int32, copy=False))
    elif pic.mode == 'I;16':
        img = torch.from_numpy(np.array(pic, np.int16, copy=False))
    else:
        img = torch.ByteTensor(torch.ByteStorage.from_buffer(pic.tobytes()))
    # PIL image mode: 1, L, P, I, F, RGB, YCbCr, RGBA, CMYK
    if pic.mode == 'YCbCr':
        nchannel = 3
    elif pic.mode == 'I;16':
        nchannel = 1
    else:
        nchannel = len(pic.mode)
    img = img.view(pic.size[1], pic.size[0], nchannel)
    # put it from HWC to CHW format
    # yikes, this transpose takes 80% of the loading time/CPU
    img = img.transpose(0, 1).transpose(0, 2).contiguous()
    if isinstance(img, torch.ByteTensor):
        return img.float()
    else:
        return img


def to_var(x, requires_grad=True):#用于将输入的张量 x 转换为 PyTorch 的 Variable 对象，并将其数据类型转换为浮点型。
    if requires_grad:
        return Variable(x).float()
    else:
        return Variable(x, requires_grad=requires_grad).float()


def copy_area(tar, src, lms):#那么这个函数可能用于提取包含眼睛的区域图像数据，然后将其复制到其他地方（比如用于图像合成、眼部特征增强等应用场景），同时清理源图像中已复制的区域，保持数据处理的一致性和合理性。
    rect = [int(min(lms[:, 1])) - PreProcess.eye_margin, 
            int(min(lms[:, 0])) - PreProcess.eye_margin, 
            int(max(lms[:, 1])) + PreProcess.eye_margin + 1, 
            int(max(lms[:, 0])) + PreProcess.eye_margin + 1]
    tar[:, :, rect[1]:rect[3], rect[0]:rect[2]] = \
        src[:, :, rect[1]:rect[3], rect[0]:rect[2]]
    src[:, :, rect[1]:rect[3], rect[0]:rect[2]] = 0


class PreProcess:
    eye_margin = 16#可能是一个常数，用于调整人脸关键点坐标的取值范围，以适应不同大小的人脸。（对应于上面函数裁剪的像素范围）
    diff_size = (64, 64)#定义为一个元组 (64, 64)，从后续代码中可以推测，它可能用于指定一些中间处理结果（比如经过插值等操作后的图像或特征相关数据）的目标尺寸大小，在涉及图像数据的尺寸调整和特征维度匹配等操作中会用到这个设定的尺寸。

    def __init__(self, config, device="cpu", need_parser=True):#
        self.device = device
        self.img_size    = config.DATA.IMG_SIZE

        xs, ys = np.meshgrid(#生成固定网格：创建一个固定网格 fix，用于后续处理。
            np.linspace(
                0, self.img_size - 1,
                self.img_size
            ),
            np.linspace(
                0, self.img_size - 1,
                self.img_size
            )
        )
        xs = xs[None].repeat(config.PREPROCESS.LANDMARK_POINTS, axis=0)#这行代码首先将 xs 数组通过 None 索引扩展为一个二维数组，然后使用 repeat 方法沿着第一个维度
        ys = ys[None].repeat(config.PREPROCESS.LANDMARK_POINTS, axis=0)#这样做的目的是为了创建一个与地标点数相同数量的水平坐标数组。
        fix = np.concatenate([ys, xs], axis=0)#能是将两个数组 ys 和 xs 沿着第0轴（即行方向）进行拼接。具体来说，np.concatenate 函数将 ys 和 xs 在第0轴上合并成一个新的数组 fix。
        self.fix = torch.Tensor(fix).to(self.device)
        if need_parser:
            self.face_parse = futils.mask.FaceParser(device=device)#这行代码创建了一个名为 face_parse 的 FaceParser 对象，用于对人脸进行解析和分割。
        self.up_ratio    = config.PREPROCESS.UP_RATIO#初始化了一系列与人脸不同区域比例相关的参数（up_ratio、down_ratio 等）以及类别相关的参数（lip_class、face_class），这些参数应该是在后续根据配置进行人脸不同部位处理（比如裁剪、调整比例等）时会用到。
        self.down_ratio  = config.PREPROCESS.DOWN_RATIO
        self.width_ratio = config.PREPROCESS.WIDTH_RATIO
        self.lip_class   = config.PREPROCESS.LIP_CLASS
        self.face_class  = config.PREPROCESS.FACE_CLASS

    def relative2absolute(self, lms):#将相对坐标转换为绝对坐标。具体功能如下：
        return lms * self.img_size#将输入的 lms（即人脸关键点坐标）乘以 img_size，以将其转换为绝对坐标。（lms=landmarks？）

    def process(self, mask, lms, device="cpu"):#该函数用于对输入的人脸图像进行预处理，包括人脸分割、关键点检测和特征提取等操作。具体功能如下：
        diff = to_var(#将 lms 转置并重塑，然后与 self.fix （self.fix 是之前在类初始化中创建的固定坐标网格）计算差异（得到坐标差值）。接着使用 unsqueeze(0) 在最前面添加一个维度，将结果包装成一个批次维度（通常在深度学习中方便同时处理多个样本，这里即使只处理一个样本也保持统一的格式），最后通过 to_var 函数将其转换为不需要计算梯度的变量（requires_grad=False）并确保在指定的 device 上。
            (self.fix.double() - torch.tensor(lms.transpose((1, 0)
                ).reshape(-1, 1, 1)).to(self.device)
            ).unsqueeze(0), requires_grad=False).to(self.device)

        lms_eye_left = lms[42:48]#从 lms 中提取左眼和右眼的特征点。（关键点固定顺序标号？左眼就是固定42-48而右眼就是固定36-42）
        lms_eye_right = lms[36:42]
        lms = lms.transpose((1, 0)).reshape(-1, 1, 1)   # transpose to (y-x)#
        # lms = np.tile(lms, (1, 256, 256))  # (136, h, w)
        diff = to_var((self.fix.double() - torch.tensor(lms).to(self.device)).unsqueeze(0), requires_grad=False).to(self.device)

        #根据 mask 生成唇部和脸部的掩码。初始化眼部掩码 mask_eyes，并将眼部区域复制到 mask_eyes 中。
        mask_lip = (mask == self.lip_class[0]).float() + (mask == self.lip_class[1]).float()
        mask_face = (mask == self.face_class[0]).float() + (mask == self.face_class[1]).float()
        mask_eyes = torch.zeros_like(mask, device=device)
        copy_area(mask_eyes, mask_face, lms_eye_left)
        copy_area(mask_eyes, mask_face, lms_eye_right)
        mask_eyes = to_var(mask_eyes, requires_grad=False).to(device)

        #将唇部、脸部和眼部的掩码合并为一个张量 mask_aug
        mask_list = [mask_lip, mask_face, mask_eyes]
        mask_aug = torch.cat(mask_list, 0)      # (3, 1, h, w)

        #对 mask_aug 和 diff 进行插值操作，使其尺寸匹配。将 diff_re 与 mask_re 相乘。计算 diff_re 的范数，并进行归一化处理
        mask_re = F.interpolate(mask_aug, size=self.diff_size).repeat(1, diff.shape[1], 1, 1)  # (3, 136, 64, 64)
        diff_re = F.interpolate(diff, size=self.diff_size).repeat(3, 1, 1, 1)  # (3, 136, 64, 64)
        diff_re = diff_re * mask_re             # (3, 136, 32, 32)
        norm = torch.norm(diff_re, dim=1, keepdim=True).repeat(1, diff_re.shape[1], 1, 1)
        norm = torch.where(norm == 0, torch.tensor(1e10, device=device), norm)
        diff_re /= norm

        return mask_aug, diff_re

    def __call__(self, image: Image):
        face = futils.dlib.detect(image)

        if not face:
            return None, None, None

        face_on_image = face[0]

        image, face, crop_face = futils.dlib.crop(
            image, face_on_image, self.up_ratio, self.down_ratio, self.width_ratio)
        np_image = np.array(image)
        mask = self.face_parse.parse(cv2.resize(np_image, (512, 512)))
        # obtain face parsing result
        # image = image.resize((512, 512), Image.ANTIALIAS)


        mask = F.interpolate(
            mask.view(1, 1, 512, 512),
            (self.img_size, self.img_size),
            mode="nearest")
        mask = mask.type(torch.uint8)
        mask = to_var(mask, requires_grad=False).to(self.device)

        # detect landmark
        lms = futils.dlib.landmarks(image, face) * self.img_size / image.width
        lms = lms.round()

        mask, diff = self.process(mask, lms, device=self.device)
        image = image.resize((self.img_size, self.img_size), Image.Resampling.LANCZOS)
        image = transform(image)
        real = to_var(image.unsqueeze(0))
        return [real, mask, diff], face_on_image, crop_face
