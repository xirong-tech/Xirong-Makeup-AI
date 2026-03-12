import logging
import shutil
import time
import uuid
from datetime import datetime
import os
import cv2
import numpy as np
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

# 初始化Flask
app = Flask(__name__)
CORS(app)
app.config.update(
    SECRET_KEY='hard to guess',
    INPUT=os.path.join(os.path.dirname(__file__), "static/input"),
    MAKEUP=os.path.join(os.path.dirname(__file__), "static/makeup"),
    TUTORIAL=os.path.join(os.path.dirname(__file__), "static/tutorial"),
    REFERENCE=os.path.join(os.path.dirname(__file__), "static/reference"),
    DESCRIBE=os.path.join(os.path.dirname(__file__), "static/describe"),
    CELERY_BROKER_URL='redis://localhost:6379/0',
    CELERY_RESULT_BACKEND='redis://localhost:6379/1'
)

# 创建目录
for folder in [app.config[k] for k in ['INPUT', 'MAKEUP', 'TUTORIAL', 'REFERENCE', 'DESCRIBE']]:
    os.makedirs(folder, exist_ok=True)

# 初始化Celery
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)


# 异步任务定义
@celery.task(bind=True)
def async_generate_content(self, makeup_path):
    try:
        # 颜色特征提取
        color_data = generate_makeup_tutorial_start(makeup_path)

        # 并行生成教程和描述
        tutorial = generate_makeup_tutorial(color_data)
        describe = generate_makeup_tutorial_describe(color_data)

        return {
            'status': 'completed',
            'tutorial': tutorial,
            'describe': describe,
            'error': None
        }
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e),
            'tutorial': None,
            'describe': None
        }


@app.route('/pic', methods=['POST'])
def handle_upload():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file_data = request.files['file']
        if not allowed_file(file_data.filename):
            return jsonify({'error': 'Invalid file type'}), 400

        # 生成唯一文件名
        filename, input_path = save_uploaded_file(file_data)

        # 处理化妆图片
        makeup_filename, makeup_path = process_makeup_image(filename, input_path)

        # 启动异步任务
        task = async_generate_content.delay(makeup_path)

        return jsonify({
            "image_url": f"https://xirong.tech/static/makeup/{makeup_filename}",
            "task_id": task.id,
            "status": "processing"
        })

    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        return jsonify({'error': str(e)}), 500


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


# Helper functions
def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in {'jpg', 'png', 'jpeg'}


def save_uploaded_file(file_data):
    filename = secure_filename(file_data.filename)
    file_uuid = uuid.uuid4().hex
    time_now = datetime.now().strftime("%Y%m%d%H%M%S")

    input_filename = f"{time_now}_{file_uuid}_{filename}"
    input_path = os.path.join(app.config['INPUT'], input_filename)
    file_data.save(input_path)

    return filename, input_path


def process_makeup_image(original_filename, input_path):
    # 生成化妆图片
    reference_pic, _ = find_face.main(input_path)
    image = makeup_transfer.main(input_path, reference_pic)

    # 保存化妆图片
    time_now = datetime.now().strftime("%Y%m%d%H%M%S")
    file_uuid = uuid.uuid4().hex
    makeup_filename = f"{time_now}_{file_uuid}_{original_filename}"
    makeup_path = os.path.join(app.config['MAKEUP'], makeup_filename)
    image.save(makeup_path)

    return makeup_filename, makeup_path


# 静态文件路由
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