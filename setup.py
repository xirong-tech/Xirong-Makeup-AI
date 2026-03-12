import argparse

from psgan import get_config

def setup_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config_file", default="configs/base.yaml", metavar="FILE", help="path to config file")
    parser.add_argument(
        "opts",
        help="Modify config options using the command-line",
        default=None,
        nargs=argparse.REMAINDER,
    )
    return parser


def setup_config(args=None):
    config = get_config()

    # 默认加载base.yaml配置
    default_config = "configs/base.yaml"

    if args:
        # 合并传入参数
        if args.config_file:
            config.merge_from_file(args.config_file)
        if args.opts:
            config.merge_from_list(args.opts)
    else:
        # 无参数时加载默认配置
        config.merge_from_file(default_config)

    config.freeze()
    return config