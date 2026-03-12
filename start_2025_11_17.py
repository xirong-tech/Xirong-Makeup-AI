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
    SHOW_FOLDER=os.path.join(os.path.dirname(__file__), "show")  # 新增展示文件夹配置
)

# 创建所需目录
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['SHOW_FOLDER'], exist_ok=True)  # 创建展示文件夹

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
        "service": "Image Upload and Process Server",
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

                # 生成唯一文件名：时间戳_UUID.扩展名
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                unique_id = uuid.uuid4().hex[:8]  # 使用短UUID
                new_filename = f"{timestamp}_{unique_id}.{file_extension}"

                # 保存文件到uploads文件夹
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                file.save(save_path)

                # 检查文件是否成功保存
                if os.path.exists(save_path):
                    saved_files.append({
                        "original_name": original_filename,
                        "saved_name": new_filename,  # 这个文件名会在处理后保持一致
                        "upload_path": f"/uploads/{new_filename}",
                        "show_path": f"/show/{new_filename}",  # 预先生成展示路径
                        "size": os.path.getsize(save_path),
                        "upload_time": timestamp,
                        "processed": False  # 初始状态：未处理
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

@app.route('/upload-to-show', methods=['POST'])
def upload_to_show():
    """
    模拟后端人员上传处理后的文件到show文件夹
    需保持与原始文件相同的文件名，以保证前端能正确匹配
    """
    try:
        if 'file' not in request.files:
            return jsonify({
                "success": False,
                "error": "未检测到文件，请使用 'file' 作为字段名"
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "success": False,
                "error": "未选择文件"
            }), 400

        # 检查文件类型（与上传接口保持一致）
        if not allowed_file(file.filename):
            return jsonify({
                "success": False,
                "error": f"文件类型不支持，仅支持: {', '.join(ALLOWED_EXTENSIONS)}"
            }), 400

        # 关键：使用前端上传时的原始保存文件名（需手动指定，或通过参数传递）
        # 这里允许通过请求参数指定文件名（确保与uploads中的文件名一致）
        target_filename = request.form.get('target_filename')
        if not target_filename:
            return jsonify({
                "success": False,
                "error": "请通过 'target_filename' 参数指定目标文件名（需与原始文件同名）"
            }), 400

        # 验证目标文件名的安全性（防止路径遍历攻击）
        target_filename = secure_filename(target_filename)
        if not allowed_file(target_filename):
            return jsonify({
                "success": False,
                "error": "目标文件名后缀不合法"
            }), 400

        # 保存到show文件夹
        save_path = os.path.join(app.config['SHOW_FOLDER'], target_filename)
        file.save(save_path)

        if os.path.exists(save_path):
            logger.info(f"处理后的文件已保存到show文件夹: {target_filename}")
            return jsonify({
                "success": True,
                "message": "处理后的文件已成功上传到show文件夹",
                "filename": target_filename,
                "show_url": f"/show/{target_filename}"
            })
        else:
            return jsonify({
                "success": False,
                "error": "文件保存失败"
            }), 500

    except Exception as e:
        logger.error(f"上传到show文件夹时出错: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"服务器内部错误: {str(e)}"
        }), 500

@app.route('/uploads/<filename>')
def serve_uploaded_file(filename):
    """提供原始上传文件的访问（供后端人员下载处理）"""
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except FileNotFoundError:
        return jsonify({"error": "文件不存在"}), 404


@app.route('/show/<filename>')
def serve_processed_file(filename):
    """提供处理后的文件访问（供前端展示）"""
    try:
        return send_from_directory(app.config['SHOW_FOLDER'], filename)
    except FileNotFoundError:
        return jsonify({"error": "处理后的文件不存在"}), 404


@app.route('/files', methods=['GET'])
def list_uploaded_files():
    """列出所有已上传的文件及其处理状态"""
    try:
        files = []
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(upload_path):
                # 检查是否已处理（即show文件夹中是否存在同名文件）
                show_path = os.path.join(app.config['SHOW_FOLDER'], filename)
                is_processed = os.path.exists(show_path)

                # 获取处理时间（如果已处理）
                processed_time = None
                if is_processed:
                    processed_time = datetime.fromtimestamp(
                        os.path.getmtime(show_path)
                    ).strftime("%Y-%m-%d %H:%M:%S")

                files.append({
                    "original_name": filename,
                    "saved_name": filename,
                    "upload_url": f"/uploads/{filename}",
                    "show_url": f"/show/{filename}" if is_processed else None,
                    "size": os.path.getsize(upload_path),
                    "upload_time": datetime.fromtimestamp(
                        os.path.getmtime(upload_path)
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    "processed": is_processed,
                    "processed_time": processed_time
                })

        return jsonify({
            "success": True,
            "file_count": len(files),
            "files": sorted(files, key=lambda x: x['upload_time'], reverse=True)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/processed-files', methods=['GET'])
def list_processed_files():
    """列出所有已处理的文件（供前端轮询）"""
    try:
        files = []
        for filename in os.listdir(app.config['SHOW_FOLDER']):
            file_path = os.path.join(app.config['SHOW_FOLDER'], filename)
            if os.path.isfile(file_path):
                files.append({
                    "name": filename,
                    "url": f"/show/{filename}",
                    "size": os.path.getsize(file_path),
                    "processed_time": datetime.fromtimestamp(
                        os.path.getmtime(file_path)
                    ).strftime("%Y-%m-%d %H:%M:%S")
                })

        return jsonify({
            "success": True,
            "file_count": len(files),
            "files": sorted(files, key=lambda x: x['processed_time'], reverse=True)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == '__main__':
    # 生产环境建议关闭debug模式，并使用Gunicorn等WSGI服务器
    app.run(host='0.0.0.0', port=5001, debug=False)