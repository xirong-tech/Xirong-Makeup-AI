from abc import ABC, abstractmethod

import dlib
import numpy as np

from imagine.imagine.functional import functional as f
from imagine.imagine.shape.figures import Rect


class BoundingBoxFinder(ABC):
    @abstractmethod
    def find(self, img):
        return NotImplemented


class DlibBoundingBoxFinder(BoundingBoxFinder):
    def __init__(self):
        super().__init__()
        self.detector = dlib.get_frontal_face_detector()

    def find(self, img):
        bbs = self.detector(img, 1)
        if len(bbs) == 0:
            return None
        biggest_bb = max(bbs, key=lambda rect: rect.width() * rect.height())
        return Rect.from_dlib(biggest_bb)


class MTCNNBoundingBoxFinder(BoundingBoxFinder):
    def __init__(self, mtcnn):
        super().__init__()
        self.mtcnn = mtcnn

    def find(self, img):
        # 确保输入是三维数组 (h, w, c)
        if len(img.shape) == 4:
            img = np.squeeze(img, axis=0)  # 移除批次维度

        # 检测人脸
        results = self.mtcnn.detect_faces(img)

        if not results:
            return None

        # 选择最大的人脸框
        biggest_face = max(results, key=lambda x: x['box'][2] * x['box'][3])
        x, y, width, height = biggest_face['box']

        # 转换为 Rect 对象（根据你的 Rect 类定义调整参数顺序）
        return Rect(y, y + height, x, x + width)