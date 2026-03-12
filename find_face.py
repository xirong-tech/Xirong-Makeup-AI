import dlib
import cv2
import numpy as np
import sys
import os


maxdist = 0

def face_locator(img):
                                                                         #脸部定位,如果有多张人脸则返回最大的人脸
    detector = dlib.get_frontal_face_detector()                          #人脸检测器
    dets = detector(img, 0)                                              #返回人脸坐标，调用检测器的 detector(img, 0) 方法，传入图像 img 和缩放参数 0，返回检测到的人脸坐标列表 dets。
    if not dets:
        return None
    return max(dets,key=lambda d:d.area())                               #TODO  #使用 max 函数和 lambda 表达式 key=lambda d: d.area() 找到面积最大的人脸并返回。
                                                                         #返回的是一个区域对象，包含人脸的左上角坐标、宽度和高度等信息。【AI】（并不包含人脸）

def extract_features(img, face_loc):                                                       #人脸特征提取 #待处理的图像 img #face_loc 通常是一个包含了人脸所在矩形区域坐标（比如左上角坐标、宽度、高度等信息）的数据结构，

                                                                                           #利用dlib的68点模型,提取特征

    predictor = dlib.shape_predictor('res/shape_predictor_68_face_landmarks.dat')          #这行代码初始化了一个 dlib 形状预测器（shape_predictor）对象，
                                                                                           # 它基于 res/shape_predictor_68_face_landmarks.dat 这个预训练模型文件。这个模型文件包含了训练好的信息，能够依据输入的人脸图像以及人脸大致位置区域，预测出人脸的 68 个关键特征点的具体坐标位置
    landmark = predictor(img, face_loc)                                                    #传入人脸图像和人脸位置，返回人脸的 68 个关键点位置。
    key_points = []
    for i in range(68):
        pos = landmark.part(i)                                                             #获取第i个关键点的坐标
                                                                                           #转换成np数组方便计算
        key_points.append(np.array([pos.x, pos.y],dtype = np.int32))                #将关键点坐标转换成np数组，选择 np.int32 数据类型是因为图像坐标通常是整数形式的像素位置。
    return key_points

def cal(std_keypoints,user_keypoints):#计算欧氏距离
    new_std=[]
    new_self=[]
    for i in range(68):
        '''
        将绝对坐标转换为相对坐标
        '''
        new_std.append(std_keypoints[i] - std_keypoints[0])
        new_self.append(user_keypoints[i] -user_keypoints[0])
    sum = 0
    for i in range(68):
        sum+=np.linalg.norm(new_std[i]-new_self[i])
    return sum

def draw(img,face_loc,dis=1):#只是在图片上画框和求距离（如果dis为1，就是调用时候没给数值用默认的，其实就是标准图，就不用在图上标出相似度）
    # （而dis不为1就是表明传入的是待检测图，要把相似度写在图上）（而dis的来源其实是关键点在经过cal函数处理后的距离）
    dist = 1-np.tanh(dis/10000)#将距离映射到0-1之间（因为最后展现的是相似率），利用了双曲正切函数（tanh）将距离映射到 0-1 之间。
    # 用dis/10000是因为tanh在x>2时就已经趋近于1，为了拉开差距要将dis给压缩到0-2之间，而欧氏距离是以像素为单位，除10000差不多是这个范围
    p1 = x1,y1 = face_loc.left(),face_loc.top()#获取人脸左上角坐标
    p2 = x2,y2 = face_loc.right(),face_loc.bottom()#获取人脸右下角坐标
    p3 = int((x1+x2)/2),y2+10#计算出一个用于放置文字信息的坐标点 p3
    cv2.rectangle(img,p1,p2,(0,0,255),2)#在图像 img 上绘制一个红色的矩形框，左上角坐标为 p1，右下角坐标为 p2，线宽为 2
    if dis!=1:#如果 dis 不等于 1，表示传入的是待检测图，需要在图上显示距离信息
        global maxdist #
        maxdist = max(maxdist,dist)#更新最大距离
        cv2.putText(img,str(maxdist),(p3),cv2.FONT_HERSHEY_SIMPLEX,0.5,(255,255,255),2)
        print(maxdist)
        # 在图上显示距离信息，位置为 p3，字体为 cv2.FONT_HERSHEY_SIMPLEX，大小为 0.5，颜色为白色，线宽为 2
    return img #返回绘制了人脸框和距离信息的图像 img

def reprocess(std_faceloc,img,user_faceloc):                             #将摄像头收到的图片按照脸框大小进行缩放,使得缩放后你的照片和标准的照片中,人脸框的大小是一样的，
                                                                         # 这是因为即使是同一张脸,向量长度也会因为脸框的大小不同而不同,这样欧氏距离就不单单是受脸型的影响了
    std_width = std_faceloc.width()                                      #获取标准人脸框的宽度
    std_height = std_faceloc.height()                                    #获取标准人脸框的高度
    user_width = user_faceloc.width()                                    #获取待检测人脸框的宽度
    user_height = user_faceloc.height()                                  #获取待检测人脸框的高度
    new_img = cv2.resize(img,None,fx = std_width/user_width,fy = std_height/user_height,\
                        interpolation = cv2.INTER_LINEAR if std_height > user_height else cv2.INTER_AREA)
    #img,传入的图像,dsize = None,第一种缩放方式,如果传入一个元组则将img缩放成以元组为长宽的图象,这里选用None是为了用第二种缩放方式
    #fx,fy,第二种方式,指定缩放比例.将原图像的边长乘以对应的比例即为新的图象边长,这里的比例是人脸框的比例,为了达到人脸框大小相同的目的
    #interpolation,插值方式,在需要放大时选用线性插值(LINEAR),缩小时采用区域插值(AREA),综合性能和效果都很不错
    return new_img                                                       #返回缩放后的图像

def find_existing_image_path(filepath_f):
    """
    根据给定的文件路径（通常是.txt对应的路径），查找对应的图片文件（.jpg、.png、.gif、.bmp）是否存在，
    如果存在则返回存在的图片文件路径，否则返回None。
    """
    extensions = ['.jpg', '.png', '.gif', '.bmp']
    for ext in extensions:
        candidate_path = os.path.splitext(filepath_f)[0] + ext
        if os.path.exists(candidate_path):
            return candidate_path
    return None




##################################--------------------这里是主函数-------------------------##################################

def main(input_pic):
    img = None  # 初始化img为None


    #################-------------这里的人脸是作为一个裁切基准，妆容图和用户图都要以这个为基准----------------------------

    std_img = cv2.imread('res/std_dingzhen.jpg')                     # 读取标准人脸图像
    std_face_loc = face_locator(std_img)                             # 获取标准人脸位置 (人脸位置是一个矩形区域)





    #################-------------输入的用户待测人脸处理--------------------------------------------

    user_img = cv2.imread(input_pic)                                                 #读取用户人脸图像
    user_face_loc = face_locator(user_img)                                           #获取拥护人脸位置
    if user_face_loc:
        new_img = reprocess(std_face_loc, user_img, user_face_loc)                   #利用reprocess函数------将待用户人脸图像按照脸框大小进行缩放
        new_face_loc = face_locator(new_img)                                         #利用face_locator函数------获取缩放后的用户人脸位置
        user_keypoints = extract_features(new_img, new_face_loc)                     #利用extract_features函数------提取缩放后的用户人脸特征 68点




    ################----------------遍历比较txt里的特征向量----------------------------------------
        folder_path = 'mydata'
        #设立一个初始哨兵
        dist_f = 0

        # 递归遍历文件夹中的所有文件
        for root, dirs, files in os.walk(folder_path):
            for filename in files:
                # 构建完整的文件路径
                file_path = os.path.join(root, filename)

                #检查文件是否是txt文件
                if filename.lower().endswith('.txt'):
                    # 读取txt文件内容
                    with open(file_path, 'r') as f:
                        lines = f.readlines()
                        keypoints = []
                        for line in lines:
                            parts = line.strip().split()

                            keypoints.append([float(part) for part in parts])
                        keypoints = np.array(keypoints)
                        # 计算相似度
                        dist = cal(keypoints, user_keypoints)
                        dist = 1 - np.tanh(dist / 10000)
                        if dist>dist_f:
                            dist_f = dist
                            filepath_f=file_path



    ################----------------找到最大相似度返回对应数据----------------------------------------
        existing_path = find_existing_image_path(filepath_f)
        if existing_path:
            # img = cv2.imread(existing_path)
            # cv2.imshow('standard!', img)
            # cv2.waitKey(0)
            # input("按任意键继续...")  # 添加这行，等待用户输入后再继续执行
            # cv2.destroyAllWindows()
            print(existing_path)
            return existing_path,dist_f
        else:
            print("没有找到对应的有效图片文件")
            return None
    else:
        print('no face')
        return None
