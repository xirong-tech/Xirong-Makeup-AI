import logging
import shutil
import time
import uuid
from datetime import datetime
from pydoc import describe

import cv2
import numpy as np
from PIL import Image
import os
from werkzeug.utils import secure_filename
import demo
import makeup_transfer
import find_face
from flask import Flask, request, send_file, jsonify, send_from_directory
import io
from flask_cors import CORS
from start_input import generate_makeup_tutorial_start
import torch
from generate_makeup_tutorial.generate_makeup_tutorial import generate_makeup_tutorial
from generate_makeup_tutorial.describe import generate_makeup_tutorial_describe


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = Flask(__name__)
CORS(app) 
app.config['SECRET_KEY'] = 'hard to guess'
app.config['INPUT'] = os.path.join(os.path.dirname(__file__), "static/input")
app.config['MAKEUP'] = os.path.join(os.path.dirname(__file__), "static/makeup")
app.config['TUTORIAL'] = os.path.join(os.path.dirname(__file__), "static/tutorial")
app.config['reference'] = os.path.join(os.path.dirname(__file__), "static/reference")
app.config['describe'] = os.path.join(os.path.dirname(__file__), "static/describe")

if not os.path.exists(app.config['MAKEUP']):
    os.makedirs(app.config['MAKEUP'])
if not os.path.exists(app.config['INPUT']):
    os.makedirs(app.config['INPUT'])
if not os.path.exists(app.config['TUTORIAL']):
    os.makedirs(app.config['TUTORIAL'])
if not os.path.exists(app.config['reference']):
    os.makedirs(app.config['reference'])
if not os.path.exists(app.config['describe']):
    os.makedirs(app.config['describe'])


ALLOWED_EXTENSIONS = {'jpg', 'png', 'jpeg'}
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET','POST'])
def index():
    return "测试成功"

@app.route('/pic', methods=['GET','POST'])
def get_pic():
    try:
        file_data = request.files['file']
        if file_data and allowed_file(file_data.filename):
            filename = secure_filename(file_data.filename)
            file_uuid = str(uuid.uuid4().hex)
            time_now = datetime.now()
            input_filename = time_now.strftime("%Y%m%d%H%M%S") + "_" + file_uuid + "_" + filename
            file_data.save(os.path.join(app.config['INPUT'], input_filename))
            input_path = os.path.join(app.config['INPUT'], input_filename)

        #################################--------------------------------------------------------------------------------------#####


            mode = "pic"    #mode用于指定测试的模式：'pic'表示单张图片/'video'表示视频检测

            input_pic = input_path #输入的未上妆用户图片

            reference_pic,dist_f =find_face.main(input_pic)  #输入的上妆参考图片（的目录）


        #################################--------------------------------------------------------------------------------------#####
            if mode == "pic":
                '''
                1、如果想要进行检测完的图片的保存，利用r_image.save("img.jpg")即可保存，直接在predict.py里进行修改即可。
                
                '''
                image = makeup_transfer.main(input_pic,reference_pic)

                ###上了妆的图片保存
                makeup_filename = time_now.strftime("%Y%m%d%H%M%S") + "_" + file_uuid + "_" + filename
                image.save(os.path.join(app.config['MAKEUP'], makeup_filename))
                makeup_path = os.path.join(app.config['MAKEUP'], makeup_filename)


                #颜色特征
                color_data = generate_makeup_tutorial_start(makeup_path)


                # 生成并保存上妆教程（文本）
                tutorial_step = generate_makeup_tutorial(color_data)
                tutorial_filename = time_now.strftime("%Y%m%d%H%M%S") + "_" + file_uuid + "_" + filename.split('.')[0] + ".txt"
                with open(os.path.join(app.config['TUTORIAL'], tutorial_filename), 'w', encoding='utf-8') as f:
                    f.write(tutorial_step)
                tutorial_path = os.path.join(app.config['TUTORIAL'], tutorial_filename)


                # 保存上妆描述
                describe = generate_makeup_tutorial_describe(color_data)
                describe_filename = time_now.strftime("%Y%m%d%H%M%S") + "_" + file_uuid + "_" + filename.split('.')[0] + ".txt"
                with open(os.path.join(app.config['describe'], describe_filename), 'w', encoding='utf-8') as f:
                    f.write(describe)
                describe_path = os.path.join(app.config['describe'], describe_filename)


                # 保存参考图片（路径）
                reference_pic_filename = time_now.strftime("%Y%m%d%H%M%S") + "_" + file_uuid + "_" + filename
                shutil.copy(reference_pic, os.path.join(app.config['reference'], reference_pic_filename))
                reference_pic_path = os.path.join(app.config['reference'], reference_pic_filename)

                #路径的输出查看
                print("用户上传的图片保存路径：",input_pic)
                print("上妆参考图片保存路径：",reference_pic_path)
                print("相似度：",dist_f)
                print("返回用户上妆图片保存路径：",makeup_path)
                print("返回用户上妆教程保存路径：",tutorial_path)
                print("返回用户上妆描述保存路径：",describe_path)


                image_np = np.array(image)
                image_np_bgr = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)

                _, img_encoded = cv2.imencode('.png', image_np_bgr)
                return jsonify({
                    "image_url": f"https://xirong.tech/static/makeup/{makeup_filename}",

                    "tutorial_url": f"https://xirong.tech/static/tutorial/{tutorial_filename}",
                    "tutorial_text": tutorial_step,   # 可选：直接返回文本内容

                    "describe_url": f"https://xirong.tech/static/describe/{describe_filename}",
                    "describe_text": describe,  # 可选：直接返回文本内容

                    # "reference_url": f"https://xirong.tech/static/reference/{reference_pic_filename}",



                })

    except Exception as e:
        import traceback
        traceback.print_exc()
        app.logger.error(f"Error processing request: {str(e)}")
        return f"Internal Server Error: {str(e)}", 500

# 静态文件路由配置
@app.route('/static/makeup/<filename>')
def serve_makeup_image(filename):
    return send_from_directory(app.config['MAKEUP'], filename)

@app.route('/static/tutorial/<filename>')
def serve_tutorial_text(filename):
    return send_from_directory(app.config['TUTORIAL'], filename)











if __name__ == "__main__":

    app.run(debug=True)



