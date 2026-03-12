import webcolors
from colormath.color_objects import sRGBColor, LabColor
from colormath.color_diff import delta_e_cie2000
from colormath.color_conversions import convert_color

def convert_color_dict(color_dict):
    """递归转换字典中的颜色数组为自然语言描述"""
    converted = {}
    for key, value in color_dict.items():
        if isinstance(value, dict):  # 处理嵌套字典
            converted[key] = convert_color_dict(value)
        elif isinstance(value, (list, tuple)) and len(value) == 3:  # 识别RGB颜色
            rgb = [int(v) for v in value]
            converted[f"{key}_rgb"] = rgb  # 保留原始RGB值
            converted[f"{key}_name"] = closest_color_name(tuple(rgb))
        else:
            converted[key] = value
    return converted

def closest_color_name(rgb):
    min_dist = float('inf')
    closest = "未知颜色"

    # 转换输入颜色到LabColor对象
    rgb_normalized = [x / 255.0 for x in rgb]
    input_rgb = sRGBColor(*rgb_normalized, is_upscaled=False)
    lab_input = convert_color(input_rgb, LabColor)  # 保持为LabColor对象

    # 遍历所有CSS3标准颜色
    for name, hex_code in webcolors.CSS3_NAMES_TO_HEX.items():
        # 转换对比颜色到LabColor对象
        r, g, b = webcolors.hex_to_rgb(hex_code)
        comp_rgb = sRGBColor(r/255.0, g/255.0, b/255.0, is_upscaled=False)
        comp_lab = convert_color(comp_rgb, LabColor)  # 保持为LabColor对象

        # 直接使用LabColor对象进行对比
        delta_e = delta_e_cie2000(lab_input, comp_lab)

        if delta_e < min_dist:
            min_dist = delta_e
            closest = name

    return closest
