# color_feature_extractor.py
import cv2
import numpy as np
import torch
from mtcnn_cv2 import MTCNN
from third_party.faceparsing.faceparsing.parser import FaceParser
from automakeup.automakeup.face.bounding import MTCNNBoundingBoxFinder
from automakeup.automakeup.face.extract import SimpleFaceExtractor
from automakeup.automakeup.feature.extract import MakeupExtractor


class MakeupFuture:
    def __init__(self,
                 device=torch.device('cpu'),
                 face_size=512,
                 bb_scale=1.5):
        # 硬件配置
        self.device = device

        # 初始化人脸检测组件
        self.bb_finder = MTCNNBoundingBoxFinder(MTCNN())

        # 初始化人脸提取器
        self.face_extractor = SimpleFaceExtractor(
            output_size=face_size,
            bb_scale=bb_scale
        )

        # 初始化颜色特征提取器
        self.parser = FaceParser(device=device)
        self.feature_extractor = MakeupExtractor(self.parser)

    def extract(self,face_img):

        # 颜色特征提取
        makeup_features = self.feature_extractor(face_img)

        # 结构化输出
        return self._format_features(makeup_features)

    def _format_features(self, features):
        """将numpy数组转换为字典结构"""
        return {
            "lipstick_color": features[0:3].tolist(),
            "eyeshadow0_color": features[3:6].tolist(),
            "eyeshadow1_color": features[6:9].tolist(),
            "eyeshadow2_color": features[9:12].tolist()
        }


# --------------------- 使用示例 ---------------------
if __name__ == "__main__":
    # 初始化提取器（固定配置）
    extractor = MakeupFuture(
        device=torch.device('cuda' if torch.cuda.is_available() else 'cpu'),
        face_size=512,
        bb_scale=1.5
    )

    # 提取特征
    result = extractor.extract("D:/pycharm/makeup_test_1/vHX466.png")

    # 打印结果
    print("妆容颜色特征：")
    for part, color in result.items():
        print(f"{part}: RGB{color}")

    print(result)
    print(result.items())