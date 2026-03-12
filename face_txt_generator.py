import dlib
import cv2
import numpy as np
import sys
import os


################-------------------------------------------------------定位人脸位置
def face_locator(img):
    '''
    脸部定位,如果有多张人脸则返回最大的人脸
    '''
    detector = dlib.get_frontal_face_detector()#人脸检测器
    dets = detector(img, 0)#返回人脸坐标，调用检测器的 detector(img, 0) 方法，传入图像 img 和缩放参数 0，返回检测到的人脸坐标列表 dets。
    if not dets:
        return None
    return max(dets,key=lambda d:d.area())#TODO  #使用 max 函数和 lambda 表达式 key=lambda d: d.area() 找到面积最大的人脸并返回。
    #返回的是一个区域对象，包含人脸的左上角坐标、宽度和高度等信息。【AI】（并不包含人脸）

################-------------------------------------------------------

################-------------------------------------------------------人脸特征提取

def extract_features(img, face_loc):#人脸特征提取 #待处理的图像 img #face_loc 通常是一个包含了人脸所在矩形区域坐标（比如左上角坐标、宽度、高度等信息）的数据结构，
    '''
    利用dlib的68点模型,提取特征
    '''
    predictor = dlib.shape_predictor('res/shape_predictor_68_face_landmarks.dat')#这行代码初始化了一个 dlib 形状预测器（shape_predictor）对象，
    # 它基于 res/shape_predictor_68_face_landmarks.dat 这个预训练模型文件。这个模型文件包含了训练好的信息，能够依据输入的人脸图像以及人脸大致位置区域，预测出人脸的 68 个关键特征点的具体坐标位置
    landmark = predictor(img, face_loc)#传入人脸图像和人脸位置，返回人脸的 68 个关键点位置。
    key_points = []
    for i in range(68):
        pos = landmark.part(i)#获取第i个关键点的坐标
        #转换成np数组方便计算
        key_points.append(np.array([pos.x, pos.y],dtype = np.int32))#将关键点坐标转换成np数组，选择 np.int32 数据类型是因为图像坐标通常是整数形式的像素位置。
    return key_points
################-------------------------------------------------------


################-------------------------------------------------------处理数据库的图像
def reprocess(std_faceloc,img,self_faceloc):#将摄像头收到的图片按照脸框大小进行缩放,使得缩放后你的照片和标准的照片中,人脸框的大小是一样的，
    # 这是因为即使是同一张脸,向量长度也会因为脸框的大小不同而不同,这样欧氏距离就不单单是受脸型的影响了
    std_width = std_faceloc.width()#获取标准人脸框的宽度
    std_height = std_faceloc.height()#获取标准人脸框的高度
    self_width = self_faceloc.width()#获取待检测人脸框的宽度
    self_height = self_faceloc.height()#获取待检测人脸框的高度
    new_img = cv2.resize(img,None,fx = std_width/self_width,fy = std_height/self_height,\
                        interpolation = cv2.INTER_LINEAR if std_height > self_height else cv2.INTER_AREA)
    #img,传入的图像,dsize = None,第一种缩放方式,如果传入一个元组则将img缩放成以元组为长宽的图象,这里选用None是为了用第二种缩放方式
    #fx,fy,第二种方式,指定缩放比例.将原图像的边长乘以对应的比例即为新的图象边长,这里的比例是人脸框的比例,为了达到人脸框大小相同的目的
    #interpolation,插值方式,在需要放大时选用线性插值(LINEAR),缩小时采用区域插值(AREA),综合性能和效果都很不错
    return new_img#返回缩放后的图像
################-------------------------------------------------------



################-------------------------------------------------------主函数进行遍历生成txt文件
def main():
    std_img = cv2.imread('res/std_dingzhen.jpg')  # 读取标准人脸图像
    std_face_loc = face_locator(std_img)  # 获取标准人脸位置 (人脸位置是一个矩形区域)
    # 指定文件夹路径
    folder_path = 'mydata'

    # 递归遍历文件夹中的所有文件
    for root, dirs, files in os.walk(folder_path):
        for filename in files:
            # 构建完整的文件路径
            file_path = os.path.join(root, filename)

            # 检查文件是否为图片（可以根据文件扩展名判断）
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                # 读取图片
                img = cv2.imread(file_path)
                if img is not None:
                    img_location = face_locator(img)
                    if img_location:
                        rep_pic=reprocess(std_face_loc,img,img_location)
                        new_face_loc = face_locator(rep_pic)
                        if new_face_loc:
                            img_keypoints = extract_features(rep_pic, new_face_loc)

                            # 构建保存关键点的文件路径
                            keypoints_file_path = os.path.splitext(file_path)[0] + '.txt'

                            # 将关键点坐标写入txt文件
                            with open(keypoints_file_path, 'w') as f:
                                for keypoint in img_keypoints:
                                    f.write(f"{keypoint[0]} {keypoint[1]}\n")
                else:
                    print(f"无法读取图片: {filename}")
            else:
                print(f"跳过非图片文件: {filename}")


if __name__ == "__main__":
    main()





