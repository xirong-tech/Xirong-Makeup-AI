from statsmodels.stats.descriptivestats import describe

from AdvancedMakeupExtractor.RGB_to_color import convert_color_dict
import cv2
from automakeup.automakeup.face.bounding import MTCNNBoundingBoxFinder
from mtcnn_cv2 import MTCNN

from automakeup.automakeup.face.extract import SimpleFaceExtractor
from AdvancedMakeupExtractor.color_feature_extractor import ColorFeature
from AdvancedMakeupExtractor.AdvancedMakeupExtractor import MakeupFuture

def initialize_components(device='cpu'):
    """集中初始化所有组件"""
    # 人脸检测模块
    mtcnn = MTCNN()
    bb_finder = MTCNNBoundingBoxFinder(mtcnn)

    # 颜色特征提取模块
    color_extractor = ColorFeature(device=device)


    # 特征提取模块
    face_extractor = SimpleFaceExtractor(output_size=512)
    feature_extractor = MakeupFuture(device=device)





    return {
        'bb_finder': bb_finder,
        'color_extractor':color_extractor,
        'face_extractor': face_extractor,
        'feature_extractor': feature_extractor,
    }


def main(image_path):
    # 初始化所有模块，指定使用cup/cuda
    components = initialize_components(device='cpu')

    # 处理流程,颜色空间转化
    img = cv2.cvtColor(cv2.imread(image_path), cv2.COLOR_BGR2RGB)

    # 人脸检测
    bb = components['bb_finder'].find(img)
    if bb is None:
        raise ValueError("未检测到人脸")

    # 人脸提取
    face = components['face_extractor'].extract(img, bb)

    #颜色提取
    color_features=components['color_extractor'].extract(face)

    # 特征提取
    features = components['feature_extractor'].extract(face)





    color_data ={
        'color': convert_color_dict(color_features),
        'features': convert_color_dict(features),

    }

    return color_data





def generate_makeup_tutorial_start(image_path):
    color_data = main(image_path)
    return color_data

