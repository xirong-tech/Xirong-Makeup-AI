from abc import ABC, abstractmethod

import numpy as np


class Results:
    def __init__(self, **kwargs):
        super().__init__()
        self.__dict__.update(kwargs)


class Recommender(ABC):
    @abstractmethod
    def recommend(self, *args):
        return NotImplemented


class MakeupRecommender(Recommender, ABC):
    class MakeupResults(Results):
        def __init__(self, skin_color, hair_color, lips_color, eyes_color, lipstick_color,
                     eyeshadow_outer_color, eyeshadow_middle_color, eyeshadow_inner_color):
            super().__init__(skin_color=skin_color, hair_color=hair_color, lips_color=lips_color,
                             eyes_color=eyes_color, lipstick_color=lipstick_color,
                             eyeshadow_outer_color=eyeshadow_outer_color,
                             eyeshadow_middle_color=eyeshadow_middle_color,
                             eyeshadow_inner_color=eyeshadow_inner_color)


class DummyRecommender(MakeupRecommender):
    def recommend(self):
        return self.MakeupResults(*np.random.randint(0, 256, (8, 3)).tolist())


class EncodingRecommender(MakeupRecommender):
    def __init__(self, bb_finder, face_extractor, feature_extractor, encoded_recommender):
        self.bb_finder = bb_finder
        self.face_extractor = face_extractor
        self.feature_extractor = feature_extractor
        self.encoded_recommender = encoded_recommender

    def recommend(self, image, features=None, color_features=None):
        if features is None or color_features is None:  # 保持原有流程兼容
            bb = self.bb_finder.find(image)
            face = self.face_extractor.extract(image, bb)
            features = self.feature_extractor(face)
            # 合并颜色特征和深度特征
            combined_features = np.concatenate([features, color_features])
            y = self.encoded_recommender.recommend(combined_features)

            # 返回格式化推荐结果（示例：返回色号列表）
            return {
                'lipstick': y[0:3].tolist(),
                'foundation': y[3:6].tolist(),
                'eyeshadow': [y[6:9].tolist(), y[9:12].tolist()]
            }