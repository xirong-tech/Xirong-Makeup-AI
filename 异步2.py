import logging
import shutil
import time
import uuid
from datetime import datetime
import os
import cv2
import numpy as np
import traceback
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from celery import Celery
from flask_cors import CORS
import demo
import makeup_transfer
import find_face
from start_input import generate_makeup_tutorial_start
from generate_makeup_tutorial.generate_makeup_tutorial import generate_makeup_tutorial
from generate_makeup_tutorial.describe import generate_makeup_tutorial_describe


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = Flask(__name__)
CORS(app)

####################################################################################
app.config.update(
    SECRET_KEY='hard to guess',
    INPUT=os.path.join(os.path.dirname(__file__), "static/input"),
    MAKEUP=os.path.join(os.path.dirname(__file__), "static/makeup"),
    TUTORIAL=os.path.join(os.path.dirname(__file__), "static/tutorial"),
    REFERENCE=os.path.join(os.path.dirname(__file__), "static/reference"),
    DESCRIBE=os.path.join(os.path.dirname(__file__), "static/describe"),
    broker_url = 'redis://localhost:6379/0',
    result_backend = 'redis://localhost:6379/1',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_serializer='json',
    accept_content=['json']
)

# 创建目录
for folder in [app.config[k] for k in ['INPUT', 'MAKEUP', 'TUTORIAL', 'REFERENCE', 'DESCRIBE']]:
    os.makedirs(folder, exist_ok=True)


#################################################################################
def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in {'jpg', 'png', 'jpeg'}

@app.route('/', methods=['GET','POST'])
def index():
    return "测试成功"

@app.route('/pic', methods=['POST'])
def handle_upload():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file_data = request.files['file']
        if not allowed_file(file_data.filename):
            return jsonify({'error': 'Invalid file type'}), 400


        ####设定保存文件的文件名
        filename = secure_filename(file_data.filename)
        file_uuid = str(uuid.uuid4().hex)
        time_now = datetime.now()
        time=time_now.strftime("%Y%m%d%H%M%S")


        ####用户上传的图片保存路径
        input_filename = time + "_" + file_uuid + "_" + filename
        file_data.save(os.path.join(app.config['INPUT'], input_filename))
        input_path = os.path.join(app.config['INPUT'], input_filename)
        print("用户上传的图片保存路径：", input_path)


        ####寻找相似度上妆参考图
        reference_pic,dist_f =find_face.main(input_path)
        ###上妆参考图片保存路径
        reference_pic_filename =time + "_" + file_uuid + "_" + filename
        shutil.copy(reference_pic, os.path.join(app.config['REFERENCE'], reference_pic_filename))
        reference_pic_path = os.path.join(app.config['REFERENCE'], reference_pic_filename)
        print("上妆参考图片保存路径：", reference_pic_path)
        print("相似度：", dist_f)


        ###用户上妆图片生成
        image = makeup_transfer.main(input_path, reference_pic)
        ###用户上妆图片保存路径
        makeup_filename = time + "_" + file_uuid + "_" + filename
        image.save(os.path.join(app.config['MAKEUP'], makeup_filename))
        makeup_path = os.path.join(app.config['MAKEUP'], makeup_filename)
        print("返回用户上妆图片保存路径：", makeup_path)


        # 启动异步任务
        task = async_generate_content.delay(makeup_path,filename,file_uuid,time)

        return jsonify({
            "image_url": f"https://xirong.tech/static/makeup/{makeup_filename}",
            "task_id": task.id,
            "status": "processing"
        })



    except Exception as e:
        import traceback
        traceback.print_exc()
        app.logger.error(f"Error processing request: {str(e)}")
        return f"Internal Server Error: {str(e)}", 500


##################################################################################
# 初始化Celery
celery = Celery(app.name, broker=app.config['broker_url'])
celery.conf.update(app.config)
@celery.task(bind=True, task_time_limit=360)  # 6分钟超时
def async_generate_content(self, makeup_path,filename,file_uuid,time):
    try:
        # 颜色特征提取
        color_data = generate_makeup_tutorial_start(makeup_path)

        # 并行生成教程和描述
        tutorial = generate_makeup_tutorial(color_data)
        describe = generate_makeup_tutorial_describe(color_data)

        # 保存上妆教程（文本）
        tutorial_filename = time + "_" + file_uuid + "_" + filename.split('.')[0] + ".txt"
        with open(os.path.join(app.config['TUTORIAL'], tutorial_filename), 'w', encoding='utf-8') as f:
            f.write(tutorial)
        tutorial_path = os.path.join(app.config['TUTORIAL'], tutorial_filename)
        print("返回用户上妆教程保存路径：", tutorial_path)

        # 保存上妆描述
        describe_filename = time + "_" + file_uuid + "_" + filename.split('.')[0] + ".txt"
        with open(os.path.join(app.config['DESCRIBE'], describe_filename), 'w', encoding='utf-8') as f:
            f.write(describe)
        describe_path = os.path.join(app.config['DESCRIBE'], describe_filename)
        print("返回用户上妆描述保存路径：", describe_path)

        return {
            'status': 'completed',
            'tutorial': tutorial_filename,  # 返回文件名
            'describe': describe_filename,  # 返回文件名
            'error': None
        }
    except Exception as e:
        logger.error(f"Async task failed: {str(e)}\n{traceback.format_exc()}")
        return {
            'status': 'failed',
            'error': str(e),
            'tutorial': None,
            'describe': None
        }
###################################################################################
@app.route('/task/<task_id>', methods=['GET'])
def get_task_status(task_id):
    task = async_generate_content.AsyncResult(task_id)

    if task.state == 'PENDING':
        response = {
            'status': 'pending',
            'progress': 0
        }
    elif task.state == 'FAILURE':
        response = {
            'status': 'failed',
            'error': str(task.info.get('error', 'Unknown error'))
        }
    else:
        response = {
            'status': task.info.get('status', 'processing'),
            'progress': 100 if task.ready() else 50,
            'tutorial': task.info.get('tutorial'),
            'describe': task.info.get('describe'),
            'error': task.info.get('error')
        }

    return jsonify(response)


@app.route('/static/makeup/<filename>')
def serve_makeup_image(filename):
    return send_from_directory(app.config['MAKEUP'], filename)


@app.route('/static/tutorial/<filename>')
def serve_tutorial_text(filename):
    return send_from_directory(app.config['TUTORIAL'], filename)


@app.route('/static/describe/<filename>')
def serve_describe_text(filename):
    return send_from_directory(app.config['DESCRIBE'], filename)


if __name__ == "__main__":
    app.run(debug=True)