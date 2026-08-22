import json
from copy import deepcopy
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.module_system.dept.model import DeptModel
from app.api.v1.module_system.dict.model import DictDataModel, DictTypeModel
from app.api.v1.module_system.menu.model import MenuModel
from app.api.v1.module_system.params.model import ParamsModel
from app.api.v1.module_system.role.model import RoleModel
from app.api.v1.module_system.user.model import UserModel, UserRolesModel
from app.api.v1.module_system.versions.model import VersionModel
from app.config.path_conf import SCRIPT_DIR
from app.core.database import async_db_session, check_db, create_tables
from app.core.logger import logger


class InitializeData:
    """初始化数据库和基础数据"""

    # 按依赖关系排序：先基础表，再关联表
    prepare_init_models: list[type] = [
        MenuModel,
        DeptModel,
        ParamsModel,
        RoleModel,
        DictTypeModel,
        DictDataModel,
        UserModel,
        UserRolesModel,
        VersionModel,
    ]

    # 树形模型：JSON 含嵌套 children，需递归创建对象
    _RECURSIVE_TABLES: set[str] = {"sys_menu", "sys_dept"}

    _MENU_UPDATE_FIELDS: tuple[str, ...] = (
        "name",
        "type",
        "order",
        "permission",
        "icon",
        "route_name",
        "route_path",
        "component_path",
        "redirect",
        "hidden",
        "keep_alive",
        "always_show",
        "title",
        "params",
        "affix",
        "link",
        "is_iframe",
        "is_hide_tab",
        "active_path",
        "show_badge",
        "show_text_badge",
        "scope",
        "status",
        "description",
    )

    async def init_db(self) -> None:
        """建表并导入种子数据"""
        await check_db()
        # await drop_tables()
        await create_tables()

        async with async_db_session() as session, session.begin():
            await self.__init_data(session)

    async def __init_data(self, db: AsyncSession) -> None:
        """按依赖顺序初始化各表种子数据"""
        dict_type_mapping: dict[str, Any] = {}

        for model in self.prepare_init_models:
            table_name = model.__tablename__

            data = await self.__load_json(table_name)
            if not data:
                logger.info(f"⏭️  跳过 {table_name} 表，无初始化数据")
                continue

            # 已有数据则跳过
            count = await db.execute(select(func.count()).select_from(model))
            if count.scalar():
                logger.info(f"⏭️  跳过 {table_name} 表数据初始化（表已有数据）")
                continue

            try:
                if table_name in self._RECURSIVE_TABLES:
                    objs = self.__create_objects_with_children(data, model)
                elif table_name == "sys_dict_type":
                    objs = []
                    for item in data:
                        obj = model(**item)
                        objs.append(obj)
                        dict_type_mapping[item["dict_type"]] = obj
                elif table_name == "sys_dict_data":
                    objs = []
                    for item in data:
                        dict_type_str = item.get("dict_type")
                        if dict_type_str not in dict_type_mapping:
                            logger.warning(f"⚠️  未找到字典类型 {dict_type_str}，跳过")
                            continue
                        item["dict_type_id"] = dict_type_mapping[dict_type_str].id
                        objs.append(model(**item))
                else:
                    objs = [model(**item) for item in data]

                if objs:
                    db.add_all(objs)
                    await db.flush()
                    logger.info(f"✅️ 已向 {table_name} 写入初始化数据")
                else:
                    logger.info(f"⏭️  跳过 {table_name} 表数据初始化（无有效数据）")

            except Exception:
                logger.error(f"❌️ 初始化 {table_name} 表数据失败")
                raise

        # 项目菜单采用独立、幂等的补充种子。即使 sys_menu 已有历史数据，
        # 也会按路由身份补齐页面、按权限身份补齐按钮。
        await self.__ensure_project_menus(db)

    @staticmethod
    def __create_objects_with_children(data: list[dict], model_class: type) -> list:
        """递归创建树形模型实例，处理嵌套 children 并注入 parent_id"""

        def _create(obj_data: dict) -> Any:
            children_data = obj_data.pop("children", [])
            obj = model_class(**obj_data)

            # 子节点通过 relationship 自动设置 parent_id
            if children_data:
                obj.children = [_create(child) for child in children_data]

            return obj

        return [_create(item) for item in data]

    async def __ensure_project_menus(self, db: AsyncSession) -> None:
        menu_data = await self.__load_json("cw_menu")
        if not menu_data:
            return

        for root in menu_data:
            await self.__upsert_menu_node(db, deepcopy(root), parent_id=None)
        logger.info("✅️ 财不外露项目菜单与按钮权限已校验")

    @staticmethod
    def __menu_identity(node_data: dict[str, Any], parent_id: int | None):
        """构建稳定且不跨菜单类型碰撞的幂等身份。"""
        permission = node_data.get("permission")
        route_name = node_data.get("route_name")
        route_path = node_data.get("route_path")
        menu_type = node_data.get("type")

        if menu_type == 3:
            if not permission:
                raise ValueError("按钮菜单必须配置 permission")
            return and_(MenuModel.type == 3, MenuModel.permission == permission)

        if route_name:
            return and_(MenuModel.type == menu_type, MenuModel.route_name == route_name)

        parent_condition = MenuModel.parent_id.is_(None) if parent_id is None else MenuModel.parent_id == parent_id
        return and_(
            MenuModel.type == menu_type,
            MenuModel.route_path == route_path,
            parent_condition,
        )

    async def __upsert_menu_node(
        self,
        db: AsyncSession,
        node_data: dict[str, Any],
        parent_id: int | None,
    ) -> MenuModel:
        children = node_data.pop("children", [])
        identity = self.__menu_identity(node_data, parent_id)
        menu = await db.scalar(select(MenuModel).where(identity).limit(1))
        payload = {field: node_data.get(field) for field in self._MENU_UPDATE_FIELDS if field in node_data}

        if menu is None:
            menu = MenuModel(**payload, parent_id=parent_id)
            db.add(menu)
            await db.flush()
        else:
            if menu.id == parent_id:
                raise ValueError(f"菜单 {menu.id} 不能成为自己的父节点")
            for field, value in payload.items():
                setattr(menu, field, value)
            menu.parent_id = parent_id
            await db.flush()

        for child in children:
            await self.__upsert_menu_node(db, deepcopy(child), parent_id=menu.id)
        return menu

    async def __load_json(self, filename: str) -> list[dict]:
        """读取并解析种子数据 JSON 文件"""
        json_path = SCRIPT_DIR / f"{filename}.json"
        if not json_path.exists():
            return []

        try:
            with open(json_path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"❌️ 解析 {json_path} 失败: {e!s}")
            raise
        except Exception as e:
            logger.error(f"❌️ 读取 {json_path} 失败: {e!s}")
            raise
