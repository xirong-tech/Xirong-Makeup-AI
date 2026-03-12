import os
import uuid
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from flask_cors import CORS

# 初始化日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask应用初始化
app = Flask(__name__)
CORS(app)

# 配置文件
app.config.update(
    SECRET_KEY='simple_upload_server_key',
    UPLOAD_FOLDER=os.path.join(os.path.dirname(__file__), "uploads"),

)

# 创建上传目录
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 允许的文件类型
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'bmp'}


def allowed_file(filename):
    """检查文件类型是否允许"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/', methods=['GET'])
def index():
    """服务状态检查"""
    return jsonify({
        "status": "running",
        "service": "Simple Image Upload Server",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route('/upload', methods=['POST'])
def upload_image():
    """
    图片上传接口
    支持单文件和多文件上传
    """
    try:
        # 检查是否有文件被上传
        if 'file' not in request.files and 'files' not in request.files:
            return jsonify({
                "success": False,
                "error": "未检测到上传文件，请使用 'file' 或 'files' 作为字段名"
            }), 400

        # 获取上传的文件
        uploaded_files = []
        if 'files' in request.files:
            # 多文件上传
            uploaded_files = request.files.getlist('files')
        elif 'file' in request.files:
            # 单文件上传
            uploaded_files = [request.files['file']]

        # 过滤掉空文件
        uploaded_files = [f for f in uploaded_files if f.filename != '']

        if not uploaded_files:
            return jsonify({
                "success": False,
                "error": "没有选择有效的文件"
            }), 400

        saved_files = []
        errors = []

        for file in uploaded_files:
            try:
                # 检查文件类型
                if not allowed_file(file.filename):
                    errors.append(f"文件 {file.filename} 类型不支持，仅支持: {', '.join(ALLOWED_EXTENSIONS)}")
                    continue

                # 生成安全的文件名
                original_filename = secure_filename(file.filename)
                file_extension = original_filename.rsplit('.', 1)[1].lower()

                # 生成唯一文件名：时间戳_UUID_原文件名
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                unique_id = uuid.uuid4().hex[:8]  # 使用短UUID
                new_filename = f"{timestamp}_{unique_id}.{file_extension}"

                # 保存文件
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                file.save(save_path)

                # 检查文件是否成功保存
                if os.path.exists(save_path):
                    saved_files.append({
                        "original_name": original_filename,
                        "saved_name": new_filename,
                        "file_path": f"/uploads/{new_filename}",
                        "size": os.path.getsize(save_path),
                        "upload_time": timestamp
                    })
                    logger.info(f"文件保存成功: {original_filename} -> {new_filename}")
                else:
                    errors.append(f"文件保存失败: {original_filename}")

            except Exception as e:
                error_msg = f"处理文件 {file.filename} 时出错: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        # 返回结果
        response_data = {
            "success": len(saved_files) > 0,
            "message": f"成功上传 {len(saved_files)} 个文件",
            "saved_files": saved_files
        }

        if errors:
            response_data["errors"] = errors

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"上传处理异常: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"服务器内部错误: {str(e)}"
        }), 500


@app.route('/uploads/<filename>')
def serve_uploaded_file(filename):
    """提供已上传文件的访问"""
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except FileNotFoundError:
        return jsonify({"error": "文件不存在"}), 404


@app.route('/files', methods=['GET'])
def list_uploaded_files():
    """列出所有已上传的文件"""
    try:
        files = []
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(file_path):
                files.append({
                    "name": filename,
                    "size": os.path.getsize(file_path),
                    "modified_time": datetime.fromtimestamp(
                        os.path.getmtime(file_path)
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    "url": f"/uploads/{filename}"
                })

        return jsonify({
            "success": True,
            "file_count": len(files),
            "files": sorted(files, key=lambda x: x['name'], reverse=True)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == '__main__':
    # 开发环境运行
    app.run(host='0.0.0.0', port=5001, debug=True)