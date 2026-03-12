import os
import json
import datetime
from flask import Flask, request, jsonify, send_from_directory
from functools import wraps
from werkzeug.utils import secure_filename

# ===================== 基础配置 =====================
app = Flask(__name__)
# 密钥（生产环境请改为随机复杂字符串）
app.config['SECRET_KEY'] = 'your-secret-key-here-2025'
# 上传/展示文件夹路径（请根据服务器实际路径修改）
app.config['UPLOAD_FOLDER'] = '/AI_makeup/AI_makeup/uploads'  # 待处理图片
app.config['SHOW_FOLDER'] = '/AI_makeup/AI_makeup/show'  # 处理完成图片
# 允许的图片格式
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
# 处理人员API密钥（生产环境建议从环境变量读取）
app.config['PROCESSOR_API_KEYS'] = {
    'processor_001': 'secure_key_001',
    'processor_002': 'secure_key_002',
    'processor_003': 'secure_key_003'# 可添加多个处理人员密钥
}
# 状态存储文件（记录处理状态，替代临时数据库）
STATUS_FILE = '/AI_makeup/AI_makeup/processing_status.json'
# 单个文件大小限制（10MB）
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024


# ===================== 工具函数 =====================
def allowed_file(filename):
    """验证文件格式是否合法"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def ensure_dir_exists(dir_path):
    """确保文件夹存在，不存在则创建"""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        app.logger.info(f"创建文件夹: {dir_path}")


def load_status():
    """加载处理状态数据（JSON文件）"""
    ensure_dir_exists(os.path.dirname(STATUS_FILE))
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            app.logger.error(f"加载状态文件失败: {e}")
            return {}
    return {}


def save_status(status_data):
    """保存处理状态数据到JSON文件"""
    ensure_dir_exists(os.path.dirname(STATUS_FILE))
    try:
        with open(STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        app.logger.error(f"保存状态文件失败: {e}")
        return False


def get_processor_from_key(api_key):
    """通过API Key获取处理人员标识"""
    for processor, key in app.config['PROCESSOR_API_KEYS'].items():
        if key == api_key:
            return processor
    return None


# ===================== 权限装饰器 =====================
def require_processor_auth(f):
    """处理人员API接口的身份验证装饰器"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 从请求头获取API Key
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({
                "success": False,
                "error": "未提供API Key，请在请求头添加 X-API-Key"
            }), 401

        # 验证API Key有效性
        processor = get_processor_from_key(api_key)
        if not processor:
            return jsonify({
                "success": False,
                "error": "无效的API Key，拒绝访问"
            }), 401

        # 将处理人员标识传入视图函数
        kwargs['processor'] = processor
        return f(*args, **kwargs)

    return decorated_function


# ===================== 核心接口 =====================
@app.route('/api/upload', methods=['POST'])
def upload_image():
    """前端小程序上传图片到uploads文件夹（核心上传接口）"""
    # 初始化文件夹
    ensure_dir_exists(app.config['UPLOAD_FOLDER'])
    ensure_dir_exists(app.config['SHOW_FOLDER'])

    # 检查请求是否包含文件
    if 'file' not in request.files:
        return jsonify({
            "success": False,
            "error": "请求中未包含图片文件"
        }), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({
            "success": False,
            "error": "未选择上传文件"
        }), 400

    # 验证文件格式
    if file and allowed_file(file.filename):
        # 生成唯一的saved_name（避免重名）
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
        ext = file.filename.rsplit('.', 1)[1].lower()
        saved_name = f"img_{timestamp}.{ext}"
        secure_saved_name = secure_filename(saved_name)  # 安全文件名

        # 保存文件到uploads文件夹
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_saved_name)
        try:
            file.save(file_path)
            app.logger.info(f"前端上传文件成功: {secure_saved_name}")

            # 返回给前端saved_name（关键！）
            return jsonify({
                "success": True,
                "message": "图片上传成功",
                "data": {
                    "saved_name": secure_saved_name,
                    "upload_time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "file_size": os.path.getsize(file_path) / 1024  # KB
                }
            }), 200
        except Exception as e:
            app.logger.error(f"保存上传文件失败: {e}")
            return jsonify({
                "success": False,
                "error": f"文件保存失败: {str(e)}"
            }), 500
    else:
        return jsonify({
            "success": False,
            "error": f"不支持的文件格式，仅允许: {','.join(app.config['ALLOWED_EXTENSIONS'])}"
        }), 400


@app.route('/api/processing/list', methods=['GET'])
@require_processor_auth
def list_pending_files(processor):
    """处理人员获取待处理图片列表（含saved_name）"""
    try:
        pending_files = []
        status_data = load_status()

        # 遍历uploads文件夹，筛选未处理/未认领的文件
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            show_path = os.path.join(app.config['SHOW_FOLDER'], filename)

            # 仅处理：文件存在 + 未处理（show文件夹无此文件）
            if os.path.isfile(upload_path) and not os.path.exists(show_path):
                # 获取文件状态（未认领/处理中）
                file_status = status_data.get(filename, {})
                status = file_status.get('status', 'pending')  # pending=未认领

                pending_files.append({
                    "saved_name": filename,
                    "upload_time": datetime.datetime.fromtimestamp(
                        os.path.getmtime(upload_path)
                    ).strftime('%Y-%m-%d %H:%M:%S'),
                    "file_size": os.path.getsize(upload_path) / 1024,  # KB
                    "status": status,
                    "processor": file_status.get('processor', None),  # 认领人
                    "claimed_time": file_status.get('claimed_time', None)
                })

        # 按上传时间倒序排序
        pending_files.sort(key=lambda x: x['upload_time'], reverse=True)

        return jsonify({
            "success": True,
            "data": {
                "pending_count": len(pending_files),
                "files": pending_files
            }
        }), 200
    except Exception as e:
        app.logger.error(f"获取待处理列表失败: {e}")
        return jsonify({
            "success": False,
            "error": f"获取列表失败: {str(e)}"
        }), 500


@app.route('/api/processing/claim', methods=['POST'])
@require_processor_auth
def claim_file(processor):
    """处理人员认领文件（标记为处理中，避免重复处理）"""
    data = request.get_json()
    if not data or 'saved_name' not in data:
        return jsonify({
            "success": False,
            "error": "参数错误，请提供saved_name"
        }), 400

    saved_name = data['saved_name']
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_name)
    show_path = os.path.join(app.config['SHOW_FOLDER'], saved_name)

    # 1. 检查文件是否存在且未处理
    if not os.path.exists(upload_path):
        return jsonify({
            "success": False,
            "error": f"文件 {saved_name} 不存在（uploads文件夹无此文件）"
        }), 404

    if os.path.exists(show_path):
        return jsonify({
            "success": False,
            "error": f"文件 {saved_name} 已处理完成（show文件夹已存在）"
        }), 400

    # 2. 检查是否已被其他人员认领
    status_data = load_status()
    if saved_name in status_data:
        file_status = status_data[saved_name]
        if file_status['status'] == 'processing':
            return jsonify({
                "success": False,
                "error": f"文件 {saved_name} 已被 {file_status['processor']} 认领（{file_status['claimed_time']}），请勿重复处理"
            }), 409

    # 3. 标记为处理中
    status_data[saved_name] = {
        "status": "processing",
        "processor": processor,
        "claimed_time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    if save_status(status_data):
        app.logger.info(f"{processor} 认领文件: {saved_name}")
        return jsonify({
            "success": True,
            "message": f"成功认领文件 {saved_name}，请尽快处理",
            "data": {
                "saved_name": saved_name,
                "download_url": f"/api/processing/download/{saved_name}",  # 下载链接
                "claimed_time": status_data[saved_name]['claimed_time']
            }
        }), 200
    else:
        return jsonify({
            "success": False,
            "error": "认领文件失败（状态保存失败）"
        }), 500


@app.route('/api/processing/release', methods=['POST'])
@require_processor_auth
def release_file(processor):
    """处理人员释放认领（放弃处理）"""
    data = request.get_json()
    if not data or 'saved_name' not in data:
        return jsonify({
            "success": False,
            "error": "参数错误，请提供saved_name"
        }), 400

    saved_name = data['saved_name']
    status_data = load_status()

    # 检查文件是否被当前人员认领
    if saved_name not in status_data:
        return jsonify({
            "success": False,
            "error": f"文件 {saved_name} 未被认领"
        }), 400

    file_status = status_data[saved_name]
    if file_status['processor'] != processor:
        return jsonify({
            "success": False,
            "error": f"无权释放：文件 {saved_name} 由 {file_status['processor']} 认领"
        }), 403

    # 释放认领（删除状态记录）
    del status_data[saved_name]
    if save_status(status_data):
        app.logger.info(f"{processor} 释放文件: {saved_name}")
        return jsonify({
            "success": True,
            "message": f"已释放文件 {saved_name}，该文件将重新进入待处理列表"
        }), 200
    else:
        return jsonify({
            "success": False,
            "error": "释放文件失败（状态保存失败）"
        }), 500


@app.route('/api/processing/download/<saved_name>', methods=['GET'])
@require_processor_auth
def download_file(processor, saved_name):
    """处理人员下载待处理图片"""
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_name)

    # 检查文件是否存在
    if not os.path.exists(upload_path):
        return jsonify({
            "success": False,
            "error": f"文件 {saved_name} 不存在"
        }), 404

    # 检查是否被当前人员认领（可选：非必须，仅做权限校验）
    status_data = load_status()
    if saved_name in status_data and status_data[saved_name]['processor'] != processor:
        return jsonify({
            "success": False,
            "error": f"无权下载：文件 {saved_name} 由 {status_data[saved_name]['processor']} 认领"
        }), 403

    # 发送文件（浏览器/Postman可直接下载）
    try:
        return send_from_directory(
            app.config['UPLOAD_FOLDER'],
            saved_name,
            as_attachment=True,  # 强制下载（而非预览）
            download_name=f"待处理_{saved_name}"  # 下载文件名
        )
    except Exception as e:
        app.logger.error(f"下载文件失败: {e}")
        return jsonify({
            "success": False,
            "error": f"下载失败: {str(e)}"
        }), 500


@app.route('/api/processing/upload-completed', methods=['POST'])
@require_processor_auth
def upload_completed_file(processor):
    """处理人员上传处理完成的图片到show文件夹"""
    # 检查是否包含文件
    if 'file' not in request.files:
        return jsonify({
            "success": False,
            "error": "请求中未包含处理完成的图片文件"
        }), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({
            "success": False,
            "error": "未选择上传文件"
        }), 400

    # 获取saved_name参数（必须和原文件一致）
    saved_name = request.form.get('saved_name')
    if not saved_name:
        return jsonify({
            "success": False,
            "error": "请提供原文件的saved_name（form参数）"
        }), 400

    # 验证文件格式
    if not allowed_file(file.filename):
        return jsonify({
            "success": False,
            "error": f"不支持的文件格式，仅允许: {','.join(app.config['ALLOWED_EXTENSIONS'])}"
        }), 400

    # 检查是否被当前人员认领
    status_data = load_status()
    if saved_name not in status_data or status_data[saved_name]['processor'] != processor:
        return jsonify({
            "success": False,
            "error": f"无权上传：文件 {saved_name} 未被你认领"
        }), 403

    # 保存到show文件夹（使用原saved_name，保证前端能匹配）
    show_path = os.path.join(app.config['SHOW_FOLDER'], saved_name)
    try:
        file.save(show_path)
        app.logger.info(f"{processor} 上传处理完成文件: {saved_name}")

        # 更新状态为已完成
        status_data[saved_name]['status'] = 'completed'
        status_data[saved_name]['completed_time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        save_status(status_data)

        return jsonify({
            "success": True,
            "message": f"处理完成的图片 {saved_name} 上传成功",
            "data": {
                "saved_name": saved_name,
                "show_url": f"/api/show/{saved_name}",  # 前端展示链接
                "completed_time": status_data[saved_name]['completed_time']
            }
        }), 200
    except Exception as e:
        app.logger.error(f"保存处理完成文件失败: {e}")
        return jsonify({
            "success": False,
            "error": f"文件保存失败: {str(e)}"
        }), 500


@app.route('/api/show/list', methods=['GET'])
def list_completed_files():
    """前端轮询获取已处理完成的图片列表"""
    try:
        completed_files = []
        for filename in os.listdir(app.config['SHOW_FOLDER']):
            show_path = os.path.join(app.config['SHOW_FOLDER'], filename)
            if os.path.isfile(show_path):
                completed_files.append({
                    "saved_name": filename,
                    "show_url": f"/api/show/{filename}",
                    "completed_time": datetime.datetime.fromtimestamp(
                        os.path.getmtime(show_path)
                    ).strftime('%Y-%m-%d %H:%M:%S'),
                    "file_size": os.path.getsize(show_path) / 1024  # KB
                })

        # 按完成时间倒序排序
        completed_files.sort(key=lambda x: x['completed_time'], reverse=True)

        return jsonify({
            "success": True,
            "data": {
                "completed_count": len(completed_files),
                "files": completed_files
            }
        }), 200
    except Exception as e:
        app.logger.error(f"获取已处理列表失败: {e}")
        return jsonify({
            "success": False,
            "error": f"获取列表失败: {str(e)}"
        }), 500


@app.route('/api/show/<saved_name>', methods=['GET'])
def show_image(saved_name):
    """前端展示处理完成的图片"""
    return send_from_directory(app.config['SHOW_FOLDER'], saved_name)


@app.route('/api/check-process-status', methods=['GET'])
def check_process_status():
    """新增：查询单个文件的处理状态"""
    # 1. 获取前端传的saved_name
    saved_name = request.args.get('saved_name')
    if not saved_name:
        return jsonify({"success": False, "error": "请提供saved_name"}), 400

    # 2. 检查是否已处理完成（show文件夹是否有该文件）
    show_path = os.path.join(app.config['SHOW_FOLDER'], saved_name)
    if os.path.exists(show_path):
        return jsonify({
            "success": True,
            "status": "completed",
            "show_url": f"/api/show/{saved_name}",
            "completed_time": datetime.datetime.fromtimestamp(
                os.path.getmtime(show_path)
            ).strftime('%Y-%m-%d %H:%M:%S')
        }), 200

    # 3. 未完成：查状态文件，判断是“处理中”还是“未认领”
    status_data = load_status()
    file_status = status_data.get(saved_name, {})
    if file_status.get('status') == 'processing':
        return jsonify({
            "success": True,
            "status": "processing",
            "processor": file_status.get('processor'),
            "claimed_time": file_status.get('claimed_time')
        }), 200
    else:
        # 未认领（还没处理人员接手）
        return jsonify({"success": True, "status": "pending"}), 200

# ===================== 启动配置 =====================
if __name__ == '__main__':
    # 初始化文件夹
    ensure_dir_exists(app.config['UPLOAD_FOLDER'])
    ensure_dir_exists(app.config['SHOW_FOLDER'])

    # 启动服务（生产环境建议用Gunicorn+Nginx）
    app.run(
        host='0.0.0.0',  # 允许外网访问
        port=5001,  # 端口可自定义
        debug=False  # 生产环境关闭debug
    )