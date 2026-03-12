import argparse
from pathlib import Path

from PIL import Image
from markdown_it.rules_block import reference

from psgan import Inference
from fire import Fire
import numpy as np

import faceutils as futils
from psgan import PostProcess
from setup import setup_config, setup_argparser


def main(pic,reference1):
    # 删除所有argparse相关代码（原第11-27行）
    # 直接使用默认配置路径
     # 默认配置文件路径

    # 手动创建args对象代替命令行参数
    class Args:
        config_file = "configs/base.yaml"
        opts = []
        speed = False
        device = "cpu"
        model_path = "assets/models/G.pth"

    args = Args()

    config = setup_config(args)

    # Using the second cpu
    inference = Inference(
        config, args.device, args.model_path)##
    postprocess = PostProcess(config)

    source =Image.open(pic).convert("RGB")

    reference = Image.open(reference1).convert("RGB")

    # Transfer the psgan from reference to source.
    image, face = inference.transfer(source, reference, with_face=True)
    if face is not None:
        source_crop = source.crop(
            (face.left(), face.top(), face.right(), face.bottom()))
        image = postprocess(source_crop, image)
        if args.speed:
            import time
            start = time.time()
            for _ in range(100):
                inference.transfer(source, reference)
            print("Time cost for 100 iters: ", time.time() - start)
    else:
        print("未检测到面部")
        image=pic# 或者返回一个默认值
    return image





