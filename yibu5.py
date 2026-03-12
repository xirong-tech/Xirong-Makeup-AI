import logging
import shutil
import uuid
import time
import os
import traceback
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from celery import Celery, group, chord, chain
from celery.result import AsyncResult
from flask_cors import CORS
import makeup_transfer
import find_face
from start_input import generate_makeup_tutorial_start
from generate_makeup_tutorial.generate_makeup_tutorial import generate_makeup_tutorial
from generate_makeup_tutorial.describe import generate_makeup_tutorial_describe

# 初始化日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask应用初始化
app = Flask(__name__)
CORS(app)

# 配置文件路径
app.config.update(
    SECRET_KEY='hard_to_guess',
    INPUT=os.path.join(os.path.dirname(__file__), "static/input"),
    MAKEUP=os.path.join(os.path.dirname(__file__), "static/makeup"),
    TUTORIAL=os.path.join(os.path.dirname(__file__), "static/tutorial"),
    REFERENCE=os.path.join(os.path.dirname(__file__), "static/reference"),
    DESCRIBE=os.path.join(os.path.dirname(__file__), "static/describe"),
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/1',
    task_serializer='json',
    accept_content=['json'],
    timezone='Asia/Shanghai',
    enable_utc=True
)

# 创建必要目录
for folder in [app.config[k] for k in ['INPUT', 'MAKEUP', 'TUTORIAL', 'REFERENCE', 'DESCRIBE']]:
    os.makedirs(folder, exist_ok=True)

# Celery初始化必须包含result_backend
celery = Celery(
    app.name,
    broker=app.config['broker_url'],
    backend=app.config['result_backend']  # 确保添加此行
)
celery.conf.update(
    result_backend=app.config['result_backend'],
    broker_connection_retry_on_startup=True  # 解决版本兼容性警告
 )
# 文件类型检查
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'jpg', 'png', 'jpeg'}

# 路由定义
@app.route('/', methods=['GET'])
def index():
    return "AI化妆师服务运行正常"

@app.route('/pic', methods=['POST'])
def handle_upload():
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未上传文件'}), 400

        file_data = request.files['file']
        if not allowed_file(file_data.filename):
            return jsonify({'error': '仅支持JPG/PNG格式'}), 400

        # 生成唯一文件名
        filename = secure_filename(file_data.filename)
        file_uuid = uuid.uuid4().hex
        time_str = datetime.now().strftime("%Y%m%d%H%M%S")
        input_filename = f"{time_str}_{file_uuid}_{filename}"
        input_path = os.path.join(app.config['INPUT'], input_filename)
        file_data.save(input_path)

        # 处理参考图和上妆图
        reference_pic, _ = find_face.main(input_path)
        reference_pic_filename = f"{time_str}_{file_uuid}_{filename}"
        shutil.copy(reference_pic, os.path.join(app.config['REFERENCE'], reference_pic_filename))
        image = makeup_transfer.main(input_path, reference_pic)
        makeup_filename = f"{time_str}_{file_uuid}_{filename}"
        image.save(os.path.join(app.config['MAKEUP'], makeup_filename))

        # 启动异步任务
        task = async_orchestrator.delay(
            os.path.join(app.config['MAKEUP'], makeup_filename),
            filename,
            file_uuid,
            time_str
        )
        return jsonify({
            "image_url": f"/static/makeup/{makeup_filename}",
            "task_id": task.id,
            "status": "processing"
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Celery任务定义
@celery.task
def generate_tutorial_task(color_data, meta):
    try:
        tutorial = generate_makeup_tutorial(color_data)
        tutorial_filename = f"{meta['time']}_{meta['file_uuid']}_{meta['filename'].split('.')[0]}.txt"
        output_path = os.path.join(app.config['TUTORIAL'], tutorial_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(tutorial if tutorial else "无有效教程内容")
        return {'type': 'tutorial', 'filename': tutorial_filename}
    except Exception as e:
        logger.error(f"教程生成失败: {str(e)}")
        return {'type': 'tutorial', 'error': str(e)}

@celery.task
def generate_describe_task(color_data, meta):
    try:
        describe = generate_makeup_tutorial_describe(color_data)
        describe_filename = f"{meta['time']}_{meta['file_uuid']}_{meta['filename'].split('.')[0]}.txt"
        output_path = os.path.join(app.config['DESCRIBE'], describe_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(describe if describe else "无有效描述内容")
        return {'type': 'describe', 'filename': describe_filename}
    except Exception as e:
        logger.error(f"描述生成失败: {str(e)}")
        return {'type': 'describe', 'error': str(e)}


# 在模块顶层定义回调任务（不要嵌套）
@celery.task(name='process_results')
def process_results(results):
    return {
        'tutorial': results[0].get('filename'),
        'describe': results[1].get('filename'),
        'status': 'completed'
    }



@celery.task(bind=True, name='async_orchestrator')
def async_orchestrator(self, makeup_path, filename, file_uuid, time_str):
    try:
        logger.info(f"【主任务启动】Task ID: {self.request.id}")
        color_data = generate_makeup_tutorial_start(makeup_path)
        meta = {'filename': filename, 'file_uuid': file_uuid, 'time': time_str}

        # 使用Group并行执行任务
        task_group = group(
            generate_tutorial_task.s(color_data, meta),
            generate_describe_task.s(color_data, meta)
        )


        # 使用Chord确保并行任务完成
        chord_task = chord(task_group)(process_results.s())
        return chord_task.get(disable_sync_subtasks=False)  # 允许异步获取

    except Exception as e:
        logger.error(f"主任务异常: {str(e)}")
        return {'status': 'failed', 'error': str(e)}

# 其他路由和工具函数
@app.route('/task/<task_id>', methods=['GET'])
def get_task_status(task_id):
    try:
        task = AsyncResult(task_id, app=celery)  # 添加 app=celery
        response = {
            'status': task.state,
            'progress': 0,
            'tutorial': None,
            'describe': None,
            'error': None
        }

        if task.state == 'SUCCESS':
            response.update({
                'progress': 100,
                'tutorial': task.result.get('tutorial'),
                'describe': task.result.get('describe')
            })
        elif task.state == 'FAILURE':
            response['error'] = str(task.result)

        return jsonify(response)
    except Exception as e:
        logger.error(f"查询任务状态失败: {str(e)}")
        return jsonify({"error": "内部服务错误"}), 500

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
    app.run(host='0.0.0.0', port=5000, debug=True)