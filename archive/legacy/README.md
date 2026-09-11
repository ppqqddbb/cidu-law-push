# 历史脚本

本目录只保留旧版本以供追溯，不属于可执行入口，也不会打入 Python 安装包。

- `run.py`：旧入口包含未定义变量，已由根目录 `run_filter.py` 及 `law-push crawl` 替代。
- `law_filter.py`：旧文本过滤器使用过时的输出格式，已由 `law_push.classifier` 和 `law_push.pipeline` 替代。

业务修改应在 `src/law_push/` 中完成。不要直接运行或引用归档脚本。
