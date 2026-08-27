import importlib
import inspect
import os
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

from sqlalchemy import inspect as sa_inspect

from app.config.path_conf import BASE_DIR
from app.core.exceptions import CustomException


class ImportUtil:
    """扫描工程中的 ORM 模型文件并做有效性校验的辅助类。"""

    @classmethod
    def find_project_root(cls) -> Path:
        """返回项目根目录（与配置中的 `BASE_DIR` 一致）。

        返回:
        - Path: 项目根路径。
        """
        return BASE_DIR

    @classmethod
    def is_valid_model(cls, obj: Any, base_class: type) -> bool:
        """判断是否为可映射的 SQLAlchemy 模型类（含表名与非空列）。

        参数:
        - obj (Any): 待验证对象（一般为类）。
        - base_class (type): ORM 声明基类。

        返回:
        - bool: 是否为有效模型类。
        """
        if not (inspect.isclass(obj) and issubclass(obj, base_class) and obj is not base_class):
            return False

        if not hasattr(obj, "__tablename__") or getattr(obj, "__tablename__", None) is None:
            return False

        try:
            inspected = sa_inspect(obj)
            return inspected is not None and len(inspected.columns) > 0
        except Exception:
            return False

    @classmethod
    @lru_cache(maxsize=256)
    def find_models(cls, base_class: type) -> list[Any]:
        """遍历工程内 `model.py` / `models.py`，收集去重后的有效模型类。

        所有模型模块先完整导入，再开始 SQLAlchemy inspection。这样可避免
        `RoleModel`、`UserModel` 等通过字符串声明的多对多关系在关联模型尚未
        注册时被过早配置，导致 mapper registry 进入不可恢复的失败状态。

        参数:
        - base_class (type): SQLAlchemy 声明基类。

        返回:
        - list[Any]: 模型类列表。

        异常:
        - ImportError: 模块导入失败（非「无法从某名导入」类警告）。
        - CustomException: 处理模块时发生未预期错误。
        """
        models: list[Any] = []
        seen_models: set[Any] = set()
        seen_tables: set[str] = set()
        processed_model_files: set[str] = set()
        imported_modules: list[ModuleType] = []

        project_root = cls.find_project_root()
        exclude_dirs = {
            "venv",
            ".env",
            ".git",
            "__pycache__",
            "migrations",
            "alembic",
            "tests",
            "test",
            "docs",
            "examples",
            "scripts",
            ".venv",
            "static",
            "templates",
            "sql",
            "env",
        }
        model_dir_patterns = ["model.py", "models.py"]

        model_files: list[tuple[Path, Path]] = []
        for root, dirs, files in os.walk(project_root):
            dirs[:] = [directory for directory in dirs if directory not in exclude_dirs]
            for file in files:
                if file not in model_dir_patterns:
                    continue
                file_path = Path(root) / file
                relative_path = file_path.relative_to(project_root)
                model_files.append((file_path, relative_path))

        model_files.sort(key=lambda item: str(item[1]))

        # 第一阶段：只导入模块。此阶段不 inspect mapper，确保字符串关系目标、
        # secondary 关联表和反向关系都先进入同一个 registry/metadata。
        for file_path, relative_path in model_files:
            normalized_path = str(file_path)
            if normalized_path in processed_model_files:
                continue
            processed_model_files.add(normalized_path)

            module_parts = (*relative_path.parts[:-1], relative_path.stem)
            module_name = ".".join(module_parts)
            try:
                imported_modules.append(importlib.import_module(module_name))
            except ImportError as exc:
                if "cannot import name" not in str(exc):
                    raise ImportError(f"❗️ 警告: 无法导入模块 {module_name}: {exc}") from exc
            except Exception as exc:
                raise CustomException(f"❌️ 导入模块 {module_name} 时出错: {exc}") from exc

        # 第二阶段：所有模块都已注册后，再校验并收集具体映射类。
        for module in imported_modules:
            try:
                for _name, obj in inspect.getmembers(module, inspect.isclass):
                    if not cls.is_valid_model(obj, base_class):
                        continue
                    if obj in seen_models:
                        continue

                    table_name = getattr(obj, "__tablename__", None)
                    if table_name is None or table_name in seen_tables:
                        continue

                    seen_models.add(obj)
                    seen_tables.add(table_name)
                    models.append(obj)
            except Exception as exc:
                raise CustomException(f"❌️ 处理模块 {module.__name__} 时出错: {exc}") from exc

        cls._find_apscheduler_model(base_class, models, seen_models, seen_tables)
        return models

    @classmethod
    def _find_apscheduler_model(
        cls,
        base_class: type,
        models: list[Any],
        seen_models: set[Any],
        seen_tables: set[str],
    ) -> None:
        """尝试从调度相关模块补充 `apscheduler_jobs` 表对应模型。"""
        try:
            for module_name in [
                "app.core.ap_scheduler",
                "app.module_task.scheduler_test",
            ]:
                try:
                    module = importlib.import_module(module_name)
                    for _name, obj in inspect.getmembers(module, inspect.isclass):
                        if cls.is_valid_model(obj, base_class) and getattr(obj, "__tablename__", None) == "apscheduler_jobs" and obj not in seen_models and "apscheduler_jobs" not in seen_tables:
                            seen_models.add(obj)
                            seen_tables.add("apscheduler_jobs")
                            models.append(obj)
                            print(f"✅️ 找到有效模型: {obj.__module__}.{obj.__name__} (表: apscheduler_jobs)")
                except ImportError:
                    pass
        except Exception as exc:
            raise CustomException(f"❗️ 查找APScheduler模型时出错: {exc}") from exc
