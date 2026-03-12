import logging
import shutil
import uuid
from datetime import datetime
import time
import os
import traceback
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from celery import Celery, states
from celery.result import AsyncResult
from flask_cors import CORS
import makeup_transfer
import find_face
from start_input import generate_makeup_tutorial_start
from generate_makeup_tutorial.generate_makeup_tutorial import generate_makeup_tutorial
from generate_makeup_tutorial.describe import generate_makeup_tutorial_describe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# 配置部分保持不变
app.config.update(
    SECRET_KEY='hard to guess',
    INPUT=os.path.join(os.path.dirname(__file__), "static/input"),
    MAKEUP=os.path.join(os.path.dirname(__file__), "static/makeup"),
    TUTORIAL=os.path.join(os.path.dirname(__file__), "static/tutorial"),
    REFERENCE=os.path.join(os.path.dirname(__file__), "static/reference"),
    DESCRIBE=os.path.join(os.path.dirname(__file__), "static/describe"),
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/1',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_serializer='json',
    accept_content=['json']
)

# 创建目录
for folder in [app.config[k] for k in ['INPUT', 'MAKEUP', 'TUTORIAL', 'REFERENCE', 'DESCRIBE']]:
    os.makedirs(folder, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'jpg', 'png', 'jpeg'}

@app.route('/', methods=['GET'])
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

        filename = secure_filename(file_data.filename)
        file_uuid = str(uuid.uuid4().hex)
        time_str = datetime.now().strftime("%Y%m%d%H%M%S")

        input_filename = f"{time_str}_{file_uuid}_{filename}"
        file_data.save(os.path.join(app.config['INPUT'], input_filename))
        input_path = os.path.join(app.config['INPUT'], input_filename)

        # 处理参考图和上妆图（保持原逻辑）
        reference_pic, dist_f = find_face.main(input_path)
        reference_pic_filename = f"{time_str}_{file_uuid}_{filename}"
        shutil.copy(reference_pic, os.path.join(app.config['REFERENCE'], reference_pic_filename))
        image = makeup_transfer.main(input_path, reference_pic)
        makeup_filename = f"{time_str}_{file_uuid}_{filename}"
        image.save(os.path.join(app.config['MAKEUP'], makeup_filename))
        makeup_path = os.path.join(app.config['MAKEUP'], makeup_filename)

        # 启动主异步任务
        task = async_orchestrator.delay(makeup_path, filename, file_uuid, time_str)
        logger.info(f"Task ID generated: {task.id}")
        return jsonify({
            "image_url": f"/static/makeup/{makeup_filename}",
            "task_id": task.id,
            "status": "processing"
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Celery初始化
celery = Celery(app.name, broker=app.config['broker_url'])
celery.conf.update(app.config)


#######################################################################
@celery.task
def generate_tutorial_task(color_data, meta):
    try:
        tutorial = generate_makeup_tutorial(color_data)

        tutorial_filename = f"{meta['time']}_{meta['file_uuid']}_{meta['filename'].split('.')[0]}.txt"
        with open(os.path.join(app.config['TUTORIAL'], tutorial_filename), 'w', encoding='utf-8') as f:
            f.write(tutorial)
        return {'type': 'tutorial', 'filename': tutorial_filename}
    except Exception as e:
        logger.error(f"生成教程失败: {str(e)}")
        return {'type': 'tutorial', 'error': str(e)}



########################################################################
@celery.task
def generate_describe_task(color_data, meta):
    try:
        describe = generate_makeup_tutorial_describe(color_data)
        # 检查返回值是否为有效字符串
        if not isinstance(describe, str):
            raise ValueError("generate_makeup_tutorial_describe 返回了非字符串内容")

        describe_filename = f"{meta['time']}_{meta['file_uuid']}_{meta['filename'].split('.')[0]}.txt"
        with open(os.path.join(app.config['DESCRIBE'], describe_filename), 'w', encoding='utf-8') as f:
            f.write(describe)
        return {'type': 'describe', 'filename': describe_filename}
    except Exception as e:
        logger.error(f"生成描述失败: {str(e)}")
        return {'type': 'describe', 'error': str(e)}

@celery.task(bind=True, task_time_limit=360)
def async_orchestrator(self, makeup_path, filename, file_uuid, time_str):
    try:
        #########################################################################################
        logger.info(f"【主任务启动】Task ID: {self.request.id}")
        color_data = generate_makeup_tutorial_start(makeup_path)

        # 新增数据日志（关键点）
        logger.info(f"生成的color_data结构: {type(color_data)}")
        logger.info(f"color_data内容样本: { {k: v for k, v in list(color_data.items())[:3]} }")  # 显示前3个键值对

        meta = {'filename': filename, 'file_uuid': file_uuid, 'time': time_str}

        # 启动子任务
        tutorial_task = generate_tutorial_task.delay(color_data, meta)
        describe_task = generate_describe_task.delay(color_data, meta)
        logger.info(f"子任务ID: 教程={tutorial_task.id}, 描述={describe_task.id}")

        # 更新状态
        self.update_state(
            state='PROGRESS',
            meta={'progress': 0, 'tutorial': None, 'describe': None}
        )

        # 轮询子任务状态
        completed = {'tutorial': False, 'describe': False}
        results = {'tutorial': None, 'describe': None}
        while not all(completed.values()):
            # 检查教程任务
            if not completed['tutorial']:
                tut_result = AsyncResult(tutorial_task.id)
                if tut_result.ready():
                    if tut_result.successful():
                        result_data = tut_result.get()
                        if 'error' in result_data:  # 检测 Dify 返回的错误
                            raise ValueError(f"教程生成错误: {result_data['error']}")
                        results['tutorial'] = result_data['filename']
                        completed['tutorial'] = True
                    else:
                        logger.error(f"教程任务失败: {tut_result.result}")

            # 检查描述任务
            if not completed['describe']:
                desc_result = AsyncResult(describe_task.id)
                if desc_result.ready():
                    if desc_result.successful():
                        results['describe'] = desc_result.get()['filename']
                        completed['describe'] = True
                        logger.info(f"描述任务完成: {results['describe']}")
                    else:
                        logger.error(f"描述任务失败: {desc_result.result}")

            # 更新进度
            progress = 50 if sum(completed.values()) == 1 else 100
            self.update_state(
                state='PROGRESS',
                meta={
                    'progress': progress,
                    'tutorial': results['tutorial'],
                    'describe': results['describe']
                }
            )
            time.sleep(1)

        return {'status': 'completed', **results}
    except Exception as e:
        logger.error(f"主任务异常: {str(e)}\n{traceback.format_exc()}")
        return {'status': 'failed', 'error': str(e)}
@app.route('/task/<task_id>', methods=['GET'])
def get_task_status(task_id):
    task = async_orchestrator.AsyncResult(task_id)
    response = {
        'status': task.state,
        'progress': 0,
        'tutorial': None,
        'describe': None,
        'error': None
    }

    if task.state == 'PROGRESS':
        response.update({
            'progress': task.info.get('progress', 0),
            'tutorial': task.info.get('tutorial'),
            'describe': task.info.get('describe')
        })
    elif task.state == 'SUCCESS':
        response.update({
            'progress': 100,
            'tutorial': task.result.get('tutorial'),
            'describe': task.result.get('describe')
        })
    elif task.state == 'FAILURE':
        response.update({
            'error': str(task.info)
        })

    return jsonify(response)

# 静态文件路由保持原样
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